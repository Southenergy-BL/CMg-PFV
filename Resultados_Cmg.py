import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(page_title="Dashboard Centrales PFV", page_icon="⚡", layout="wide")

# Función para aplicar formato numérico chileno
def formato_chileno(valor):
    if pd.isna(valor):
        return "-"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.title("⚡ Dashboard Interactivo: Análisis de Centrales Fotovoltaicas (PFV)")
st.markdown("Análisis de Costos Marginales, Factibilidad BESS, Ranking de Mercado y Estados Operativos.")

# Definición global de columnas numéricas
columnas_numericas = [
    'CMg precio captura', 
    'CMg promedio horario', 
    'CMg promedio solar', 
    'CMg promedio noche', 
    'Porcentaje iny. costo cero',
    'Potencia máxima bruta Central [MW]',
    'Vertimientos [GWh]',
    'Vertimientos [%]'
]

# 2. Cargar y procesar datos multi-año
@st.cache_data
def load_data_multiaño():
    ruta_archivo = "BD Centrales.xlsx" 
    años = [2023, 2024, 2025]
    dfs_años = []
    
    try:
        for ano in años:
            nombre_hoja = f'BD Centrales {ano}'
            try:
                df_ano = pd.read_excel(ruta_archivo, sheet_name=nombre_hoja)
                df_filtrado = df_ano[df_ano['Nombre Central Infotécnica'].str.startswith('PFV', na=False)].copy()
                df_filtrado['Año'] = ano
                dfs_años.append(df_filtrado)
            except Exception:
                continue 
    except Exception:
        try:
            df_ano = pd.read_csv("BD Centrales ejemplo.xlsx - BD Centrales 2025.csv")
            df_filtrado = df_ano[df_ano['Nombre Central Infotécnica'].str.startswith('PFV', na=False)].copy()
            df_filtrado['Año'] = 2025
            dfs_años.append(df_filtrado)
        except Exception:
            pass
            
    if not dfs_años:
        return pd.DataFrame()
        
    df_completo = pd.concat(dfs_años, ignore_index=True)
    
    for col in columnas_numericas:
        if col in df_completo.columns:
            if df_completo[col].dtype == object:
                def limpiar_numero(x):
                    x = str(x).strip()
                    if '.' in x and ',' in x:
                        if x.rfind(',') > x.rfind('.'):  
                            return x.replace('.', '').replace(',', '.')
                        else:  
                            return x.replace(',', '')
                    elif ',' in x:
                        return x.replace(',', '.')
                    return x
                    
                df_completo[col] = df_completo[col].apply(limpiar_numero)
            df_completo[col] = pd.to_numeric(df_completo[col], errors='coerce')
    
    df_completo = df_completo.dropna(subset=['Potencia máxima bruta Central [MW]'])
    df_completo['Eficiencia de Captura (%)'] = (df_completo['CMg precio captura'] / df_completo['CMg promedio horario']) * 100
    df_completo['Spread Día-Noche'] = df_completo['CMg promedio noche'] - df_completo['CMg promedio solar']
    
    return df_completo

# Cargar Datos de Ranking
@st.cache_data
def load_ranking_data():
    try:
        df = pd.read_csv("BD Centrales - Extra.xlsx - Ranking PFV.csv")
    except FileNotFoundError:
        try:
            df = pd.read_excel("BD Centrales - Extra.xlsx", sheet_name="Ranking PFV")
        except FileNotFoundError:
            return pd.DataFrame()
            
    columnas_ranking = [
        'Score Técnico 2025',
        'Score Técnico Promedio', 
        'PPA mínimo 2025 [USD/MWh]', 
        'PPA mínimo Promedio [USD/MWh]', 
        'Score Comercial 2025', 
        'Score Comercial Promedio'
    ]
    
    for c in columnas_ranking:
        if c in df.columns:
            df[c] = df[c].astype(str).replace('-', pd.NA).str.replace(',', '.')
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
    if '¿Tiene BESS?' in df.columns:
        df['¿Tiene BESS?'] = df['¿Tiene BESS?'].astype(str).replace('-', 'No').replace('nan', 'No').fillna('No')
            
    return df

# --- NUEVO: Cargar datos consolidados de estados operativos ---
@st.cache_data
def load_consolidados_data():
    try:
        # 1. Cargar el CSV (con el separador correcto que encontramos antes)
        df = pd.read_csv("consolidados_2026-08-18_15_58_31.csv")
        
        # 2. LIMPIEZA DE LA COLUMNA DURACIÓN
        if 'duracion' in df.columns:
            # Reemplazamos las comas por puntos (por si vienen con formato chileno)
            df['duracion'] = df['duracion'].astype(str).str.replace(',', '.')
            # Convertimos explícitamente a número, ignorando textos extraños
            df['duracion'] = pd.to_numeric(df['duracion'], errors='coerce')
            
        return df
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer el CSV de consolidados: {e}")
        return pd.DataFrame()

# Ejecutar cargas
df_pfv = load_data_multiaño()
df_ranking = load_ranking_data()
df_consolidados = load_consolidados_data() # NUEVO

if df_pfv.empty:
    st.error("No se encontraron los datos principales (CMg). Verifica los nombres de los archivos.")
else:
    # --- BARRA LATERAL (FILTROS GENERALES) ---
    st.sidebar.header("Filtros Base")
    años_disponibles = sorted(list(df_pfv['Año'].unique()), reverse=True)
    ano_sel = st.sidebar.selectbox("Año de Análisis", años_disponibles)
    
    df_por_ano = df_pfv[df_pfv['Año'] == ano_sel]
    centrales_disponibles = ["Todas"] + sorted(list(df_por_ano['Nombre Central Infotécnica'].unique()))
    central_sel = st.sidebar.selectbox("Consultar Central Específica", centrales_disponibles)
    
    if central_sel == "Todas":
        min_pot = float(df_por_ano['Potencia máxima bruta Central [MW]'].min())
        max_pot = float(df_por_ano['Potencia máxima bruta Central [MW]'].max())
        
        val_min_defecto = 20.0 if min_pot <= 20.0 <= max_pot else min_pot
        val_max_defecto = 200.0 if min_pot <= 200.0 <= max_pot else max_pot
        
        if val_min_defecto > val_max_defecto:
            val_min_defecto, val_max_defecto = min_pot, max_pot
        
        potencia_rango = st.sidebar.slider(
            "Rango de Potencia [MW]", 
            min_value=min_pot, 
            max_value=max_pot, 
            value=(val_min_defecto, val_max_defecto)
        )
        mask = df_por_ano['Potencia máxima bruta Central [MW]'].between(potencia_rango[0], potencia_rango[1])
        df_plot = df_por_ano[mask]
    else:
        df_plot = df_por_ano[df_por_ano['Nombre Central Infotécnica'] == central_sel]

    st.sidebar.divider()
    st.sidebar.header("⚙️ Configuración BESS")
    horas_bess = st.sidebar.slider(
        "Duración del Almacenamiento (Horas)", 
        min_value=1, max_value=8, value=4, step=1,
        help="Define las horas de descarga para dimensionar el inversor."
    )

    # --- ORGANIZACIÓN EN PESTAÑAS (Modificado para incluir Tab 4) ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Análisis CMg", "🔋 Evaluación BESS", "🏆 Ranking y Scores", "⏱️ Estados Operativos"])

    # =========================================================================
    # TAB 1: ANÁLISIS DE MERCADO Y CMG
    # =========================================================================
    with tab1:
        if central_sel != "Todas" and not df_plot.empty:
            row = df_plot.iloc[0]
            st.subheader(f"🔍 Ficha Técnica y Comercial: {row['Nombre Central Infotécnica']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Capacidad Bruta", f"{formato_chileno(row['Potencia máxima bruta Central [MW]'])} MW")
            c2.metric("CMg Precio Captura", f"{formato_chileno(row['CMg precio captura'])} USD/MWh")
            c3.metric("Inyección a Costo Cero", f"{formato_chileno(row['Porcentaje iny. costo cero'])} %")
            c4.metric("Eficiencia de Captura", f"{formato_chileno(row['Eficiencia de Captura (%)'])} %")
            
            precios_planta = pd.DataFrame({
                'Bloque Horario': ['Captura', 'Prom. Horario', 'Prom. Solar', 'Prom. Noche'],
                'USD/MWh': [row['CMg precio captura'], row['CMg promedio horario'], row['CMg promedio solar'], row['CMg promedio noche']]
            })
            fig_bar = px.bar(precios_planta, x='Bloque Horario', y='USD/MWh', text='USD/MWh', template='plotly_white')
            fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)

        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Centrales Filtradas", len(df_plot))
            c2.metric("CMg Promedio Captura", f"{formato_chileno(df_plot['CMg precio captura'].mean())}")
            c3.metric("Inyección Costo Cero Prom.", f"{formato_chileno(df_plot['Porcentaje iny. costo cero'].mean())}%")
            c4.metric("Capacidad Total", f"{formato_chileno(df_plot['Potencia máxima bruta Central [MW]'].sum())} MW")

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                fig1 = px.scatter(
                    df_plot, x='Porcentaje iny. costo cero', y='CMg precio captura',
                    size='Potencia máxima bruta Central [MW]', hover_name='Nombre Central Infotécnica',
                    template='plotly_white', title="Impacto Inyección Costo Cero"
                )
                st.plotly_chart(fig1, use_container_width=True)
            with col_chart2:
                cmg_cols = ['CMg precio captura', 'CMg promedio horario', 'CMg promedio solar', 'CMg promedio noche']
                df_melted = df_plot.melt(id_vars=['Nombre Central Infotécnica'], value_vars=[c for c in cmg_cols if c in df_plot.columns])
                fig2 = px.box(df_melted, x='variable', y='value', color='variable', points="all", template='plotly_white', title="Distribución de CMg")
                fig2.update_layout(showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)

    # =========================================================================
    # TAB 2: MÓDULO BESS
    # =========================================================================
    with tab2:
        st.subheader("🔋 Evaluación de Pre-Factibilidad: Integración BESS")
        
        if 'Vertimientos [GWh]' in df_plot.columns and 'Spread Día-Noche' in df_plot.columns:
            analisis_multiano = st.checkbox("🔄 Extender análisis a todo el histórico disponible (Todos los años)", value=False)
            
            if analisis_multiano:
                df_bess_base = df_pfv[df_pfv['Nombre Central Infotécnica'] == central_sel].copy() if central_sel != "Todas" else df_pfv.copy()
            else:
                df_bess_base = df_plot.copy()
                
            df_bess_base['BESS_Capacidad_MWh'] = (df_bess_base['Vertimientos [GWh]'] * 1000) / 365
            df_bess_base['BESS_Potencia_MW'] = df_bess_base['BESS_Capacidad_MWh'] / horas_bess
            df_bess_base['Upside_Económico_Anual_USD'] = df_bess_base['Vertimientos [GWh]'] * 1000 * df_bess_base['Spread Día-Noche']
            
            df_bess_clean = df_bess_base.dropna(subset=['Upside_Económico_Anual_USD', 'BESS_Potencia_MW'])
            
            if central_sel != "Todas" and not df_bess_clean.empty:
                if analisis_multiano:
                    st.markdown(f"**Evolución Multi-Año del Potencial BESS para {central_sel}**")
                    fig_evo = px.bar(
                        df_bess_clean, x='Año', y='Upside_Económico_Anual_USD', color='Año', 
                        text='Upside_Económico_Anual_USD', template='plotly_white'
                    )
                    fig_evo.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                    fig_evo.update_layout(xaxis=dict(type='category'))
                    st.plotly_chart(fig_evo, use_container_width=True)
                else:
                    row_bess = df_bess_clean.iloc[0]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Potencia BESS Sugerida", f"{formato_chileno(row_bess['BESS_Potencia_MW'])} MW")
                    c2.metric("Capacidad BESS", f"{formato_chileno(row_bess['BESS_Capacidad_MWh'])} MWh")
                    c3.metric("Upside Teórico Anual", f"USD {formato_chileno(row_bess['Upside_Económico_Anual_USD'])}")
            
            elif not df_bess_clean.empty:
                if analisis_multiano:
                    st.markdown("**Top Centrales: Upside Acumulado Histórico**")
                    df_agrupado = df_bess_clean.groupby('Nombre Central Infotécnica').agg({
                        'Upside_Económico_Anual_USD': 'sum', 'BESS_Potencia_MW': 'mean'
                    }).reset_index()
                    top_bess = df_agrupado.sort_values(by='Upside_Económico_Anual_USD', ascending=False).head(10)
                else:
                    st.markdown(f"**Top 10 Centrales con Mayor Potencial para BESS en {ano_sel}**")
                    top_bess = df_bess_clean.sort_values(by='Upside_Económico_Anual_USD', ascending=False).head(10)
                
                fig_bess = px.bar(
                    top_bess, x='Nombre Central Infotécnica', y='Upside_Económico_Anual_USD', color='BESS_Potencia_MW',
                    color_continuous_scale='Viridis', template='plotly_white'
                )
                st.plotly_chart(fig_bess, use_container_width=True)
            else:
                st.warning("No hay suficientes datos válidos para calcular el ranking BESS en la selección actual.")
        else:
            st.error("⚠️ Faltan las columnas de Vertimientos o Spread para este cálculo.")

    # =========================================================================
    # TAB 3: RANKING Y SCORES (SCATTER PLOTS)
    # =========================================================================
    with tab3:
        st.subheader("🏆 Análisis de Scores: Técnico vs Comercial y PPA")
        st.markdown("Visualización de las evaluaciones. El tamaño del círculo indica plantas que empatan en la misma coordenada.")
        
        if df_ranking.empty:
            st.error("⚠️ No se pudo cargar el archivo de Ranking. Asegúrate de que está en la misma carpeta.")
        else:
            nombre_col_planta = df_ranking.columns[0]
            
            def graficar_scatter_dinamico(df, x_col, y_col, titulo):
                if x_col not in df.columns or y_col not in df.columns:
                    st.warning(f"Faltan datos para: {titulo}. Columnas no encontradas.")
                    return
                
                validos = df.dropna(subset=[x_col, y_col]).copy()
                faltantes = df[df[x_col].isna() | df[y_col].isna()][nombre_col_planta].tolist()
                
                if validos.empty:
                    st.warning(f"No hay datos para renderizar: {titulo}")
                    return
                
                if 'Propietario' in validos.columns:
                    validos['Info_Hover'] = validos[nombre_col_planta] + " (" + validos['Propietario'].astype(str) + ")"
                else:
                    validos['Info_Hover'] = validos[nombre_col_planta]
                
                groupby_cols = [x_col, y_col]
                tiene_bess = '¿Tiene BESS?' in validos.columns
                if tiene_bess:
                    groupby_cols.append('¿Tiene BESS?')
                
                agrupado = validos.groupby(groupby_cols).agg(
                    Lista_Centrales=('Info_Hover', lambda x: '<br>'.join(x)),
                    Cantidad_Plantas=('Info_Hover', 'count')
                ).reset_index()
                
                fig_kwargs = {
                    "x": x_col,
                    "y": y_col,
                    "size": 'Cantidad_Plantas',
                    "hover_name": 'Lista_Centrales',
                    "title": titulo,
                    "template": 'plotly_white',
                    "size_max": 30
                }
                
                if tiene_bess:
                    fig_kwargs['color'] = '¿Tiene BESS?'
                    fig_kwargs['color_discrete_map'] = {
                        'Existente': '#2ca02c',     
                        'Construcción': '#ff7f0e',  
                        'Autorizado Construcción': "#ff0e0e",  
                        'Proceso SAC': "#c713cd",  
                        'No': '#1f77b4'             
                    }
                else:
                    fig_kwargs['color_discrete_sequence'] = ['#1f77b4']
                
                fig = px.scatter(agrupado, opacity=0.6, **fig_kwargs)
                
                fig.update_traces(
                    hovertemplate="<b>Central(es) y Coordinado:</b><br>%{hovertext}<br><br>" +
                                  "<b>" + x_col + ":</b> %{x}<br>" +
                                  "<b>" + y_col + ":</b> %{y}<br>" +
                                  "<b>Total Empates:</b> %{marker.size}<extra></extra>"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if faltantes:
                    with st.expander(f"⚠️ {len(faltantes)} centrales sin score para graficar en este panel"):
                        st.write(", ".join(faltantes))

            col_rank1, col_rank2 = st.columns(2)
            
            with col_rank1:
                graficar_scatter_dinamico(df_ranking, 'Score Técnico 2025', 'PPA mínimo 2025 [USD/MWh]', "Técnico vs PPA Mínimo (2025)")
                st.divider()
                graficar_scatter_dinamico(df_ranking, 'Score Técnico 2025', 'Score Comercial 2025', "Técnico vs Score Comercial (2025)")
                
            with col_rank2:
                graficar_scatter_dinamico(df_ranking, 'Score Técnico Promedio', 'PPA mínimo Promedio [USD/MWh]', "Técnico vs PPA Mínimo (Promedio)")
                st.divider()
                graficar_scatter_dinamico(df_ranking, 'Score Técnico Promedio', 'Score Comercial Promedio', "Técnico vs Score Comercial (Promedio)")

    # =========================================================================
    # NUEVO: TAB 4: ESTADOS OPERATIVOS (AGRUPADO)
    # =========================================================================
    with tab4:
        st.subheader("⏱️ Análisis de Duración por Estado Operativo")
        
        if df_consolidados.empty:
            st.error("⚠️ No se pudo cargar el archivo de consolidados. Asegúrate de que está en la misma ruta.")
        else:
            col_central_consolidados = 'central_nombre' 
            
            if col_central_consolidados not in df_consolidados.columns:
                st.warning(f"La columna '{col_central_consolidados}' no fue encontrada en el archivo.")
            elif 'estado_operativo_nombre' not in df_consolidados.columns or 'duracion' not in df_consolidados.columns:
                st.warning("El archivo CSV debe contener las columnas 'estado_operativo_nombre' y 'duracion'.")
            else:
                centrales_validas = sorted(list(df_plot['Nombre Central Infotécnica'].unique()))
                
                if not centrales_validas:
                    st.info("No hay centrales disponibles bajo los filtros actuales para analizar.")
                else:
                    central_analisis = st.selectbox(
                        "Selecciona la central a visualizar:", 
                        options=centrales_validas
                    )
                    
                    df_ops_planta = df_consolidados[df_consolidados[col_central_consolidados] == central_analisis].copy()
                    
                    if df_ops_planta.empty:
                        st.info(f"No hay registros de estados operativos en el archivo consolidados para: {central_analisis}")
                    else:
                        # 1. Crear el diccionario de mapeo según la Tabla 5.1 de la imagen
                        diccionario_estados = {
                            'N': 'Estado Disponible', 'DN': 'Estado Disponible', 'CSE': 'Estado Disponible',
                            'DP': 'Estado No Disponible', 'DF': 'Estado No Disponible', 'MM': 'Estado No Disponible', 
                            'PMM': 'Estado No Disponible', 'FE': 'Estado No Disponible',
                            'LP': 'Estado Deteriorado', 'LF': 'Estado Deteriorado', 'DLP': 'Estado Deteriorado', 
                            'DLF': 'Estado Deteriorado', 'DRO': 'Estado Deteriorado', 'PO': 'Estado Deteriorado', 
                            'PDO': 'Estado Deteriorado', 'RO': 'Estado Deteriorado'
                        }
                        
                        # 2. Asignar la categoría principal a cada fila
                        # Si encuentra un estado que no está en la tabla, lo clasificará como 'Otros'
                        df_ops_planta['Categoria_Principal'] = df_ops_planta['estado_operativo_nombre'].map(diccionario_estados).fillna('Otros')
                        
                        # 3. Agrupar por la categoría principal y el estado específico
                        df_ops_agrupado = df_ops_planta.groupby(["Categoria_Principal", "estado_operativo_nombre"], as_index=False)["duracion"].sum()
                        
                        # Orden visual de las categorías
                        orden_categorias = ['Estado Disponible', 'Estado Deteriorado', 'Estado No Disponible', 'Otros']
                        
                        # 4. Generar histograma (coloreado y agrupado por la nueva categoría)
                        fig_ops = px.bar(
                            df_ops_agrupado,
                            x="estado_operativo_nombre",
                            y="duracion",
                            color="Categoria_Principal", 
                            text="duracion",
                            title=f"Suma Total de Duraciones por Estado: {central_analisis}",
                            labels={
                                "estado_operativo_nombre": "Sigla Estado Operativo",
                                "duracion": "Duración Total (Horas)",
                                "Categoria_Principal": "Clasificación"
                            },
                            category_orders={"Categoria_Principal": orden_categorias},
                            template="plotly_white",
                            color_discrete_map={
                                'Estado Disponible': '#2ca02c',       # Verde
                                'Estado Deteriorado': '#ff7f0e',      # Naranja
                                'Estado No Disponible': '#d62728',    # Rojo
                                'Otros': '#7f7f7f'                    # Gris
                            }
                        )
                        
                        # Formato numérico de las etiquetas sobre las barras
                        fig_ops.update_traces(texttemplate='%{text:,.2f}', textposition='outside')
                        
                        # Ajustar el diseño: habilitar leyenda para ver las categorías, y rotar etiquetas del eje X
                        fig_ops.update_layout(
                            xaxis_tickangle=-45, 
                            legend_title_text="Clasificación General",
                            xaxis={'categoryorder':'category ascending'} # Ordena alfabéticamente las barras en el eje X
                        )
                        
                        st.plotly_chart(fig_ops, use_container_width=True)