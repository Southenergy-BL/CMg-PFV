import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(page_title="Dashboard Centrales PFV Multi-Año", layout="wide")

# Función para aplicar formato numérico chileno (puntos miles, comas decimales)
def formato_chileno(valor):
    if pd.isna(valor):
        return "-"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.title("⚡ Dashboard Interactivo: Análisis de Centrales Fotovoltaicas (PFV)")
st.markdown("Análisis histórico y específico de costos marginales e inyección a costo cero.")

# Definición global de columnas numéricas
columnas_numericas = [
    'CMg precio captura', 
    'CMg promedio horario', 
    'CMg promedio solar', 
    'CMg promedio noche', 
    'Porcentaje iny. costo cero',
    'Potencia máxima bruta Central [MW]'
]

# 2. Cargar y procesar datos multi-año con caché
@st.cache_data
def load_data_multiaño():
    ruta_archivo = "BD Centrales.xlsx"
    años = [2023, 2024, 2025]
    dfs_años = []
    
    for ano in años:
        nombre_hoja = f'BD Centrales {ano}'
        try:
            # Leer la hoja correspondiente al año
            df_ano = pd.read_excel(ruta_archivo, sheet_name=nombre_hoja)
            
            # Filtrar solo PFV
            df_filtrado = df_ano[df_ano['Nombre Central Infotécnica'].str.startswith('PFV', na=False)].copy()
            
            # Asignar columna de año para trazabilidad
            df_filtrado['Año'] = ano
            dfs_años.append(df_filtrado)
        except Exception as e:
            # Si una hoja no existe o falla, continúa con las demás sin romper la app
            st.warning(f"No se pudo cargar la hoja para el año {ano}. Detalle: {e}")
            continue
            
    if not dfs_años:
        return pd.DataFrame()
        
    # Concatenar todos los años cargados
    df_completo = pd.concat(dfs_años, ignore_index=True)
    
    # Limpieza y conversión numérica
    for col in columnas_numericas:
        if col in df_completo.columns:
            if df_completo[col].dtype == object:
                df_completo[col] = df_completo[col].astype(str).str.replace(',', '.')
            df_completo[col] = pd.to_numeric(df_completo[col], errors='coerce')
    
    # Eliminar filas sin potencia válida
    df_completo = df_completo.dropna(subset=['Potencia máxima bruta Central [MW]'])
    
    # Calcular KPIs globales
    df_completo['Eficiencia de Captura (%)'] = (df_completo['CMg precio captura'] / df_completo['CMg promedio horario']) * 100
    df_completo['Spread Día-Noche'] = df_completo['CMg promedio noche'] - df_completo['CMg promedio solar']
    
    return df_completo

# Ejecutar la nueva carga unificada
df_pfv = load_data_multiaño()

if df_pfv.empty:
    st.error("No se encontraron datos en las hojas especificadas del archivo Excel.")
else:
    # --- BARRA LATERAL (FILTROS) ---
    st.sidebar.header("Filtros de Análisis")
    
    # Filtro 1: Selección de Año (Multiselect o Selectbox)
    años_disponibles = sorted(list(df_pfv['Año'].unique()), reverse=True)
    ano_sel = st.sidebar.selectbox("Año de Análisis", años_disponibles)
    
    # Filtrar por año primero para actualizar dinámicamente los demás filtros
    df_por_ano = df_pfv[df_pfv['Año'] == ano_sel]
    
    # Filtro 2: Selección de Central Específica (¡NUEVO!)
    centrales_disponibles = ["Todas"] + sorted(list(df_por_ano['Nombre Central Infotécnica'].unique()))
    central_sel = st.sidebar.selectbox("Consultar Central Específica", centrales_disponibles)
    
    # Filtros adicionales (solo visibles si se selecciona "Todas")
    if central_sel == "Todas":
        # Filtro de Potencia
        min_pot_real = float(df_por_ano['Potencia máxima bruta Central [MW]'].min())
        max_pot_real = float(df_por_ano['Potencia máxima bruta Central [MW]'].max())
        
        val_min = 20.0 if min_pot_real <= 20.0 else min_pot_real
        val_max = 200.0 if max_pot_real >= 200.0 else max_pot_real
        
        potencia_rango = st.sidebar.slider(
            "Rango de Potencia [MW]", 
            min_value=min_pot_real, 
            max_value=max_pot_real, 
            value=(val_min, val_max)
        )
        
        # Filtro de Región
        if 'Región' in df_por_ano.columns:
            regiones = ["Todas"] + sorted(list(df_por_ano['Región'].dropna().unique()))
            region_sel = st.sidebar.selectbox("Región", regiones)
        else:
            region_sel = "Todas"
            
        # Aplicar máscaras agregadas
        mask = df_por_ano['Potencia máxima bruta Central [MW]'].between(potencia_rango[0], potencia_rango[1])
        if region_sel != "Todas":
            mask = mask & (df_por_ano['Región'] == region_sel)
        df_plot = df_por_ano[mask]
        
    else:
        # Si se selecciona una sola central, se aísla su fila directamente
        df_plot = df_por_ano[df_por_ano['Nombre Central Infotécnica'] == central_sel]


    # --- RENDERIZADO DEL DASHBOARD ---
    
    # CASO A: VISTA DE UNA CENTRAL ESPECÍFICA
    if central_sel != "Todas" and not df_plot.empty:
        row = df_plot.iloc[0]
        st.subheader(f"🔍 Ficha Técnica y Comercial: {row['Nombre Central Infotécnica']} ({ano_sel})")
        
        # Panel de Métricas Destacadas de la Planta
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Capacidad Bruta", f"{formato_chileno(row['Potencia máxima bruta Central [MW]'])} MW")
            if 'Región' in row: st.caption(f"Ubicación: {row['Región']}")
        with c2:
            st.metric("CMg Precio Captura", f"{formato_chileno(row['CMg precio captura'])} USD/MWh")
        with c3:
            st.metric("Inyección a Costo Cero", f"{formato_chileno(row['Porcentaje iny. costo cero'])} %")
        with c4:
            st.metric("Eficiencia de Captura", f"{formato_chileno(row['Eficiencia de Captura (%)'])} %")
            
        st.write("---")
        
        # Gráfico comparativo de precios internos de la planta
        st.markdown(f"**Desglose de Costos Marginales de la Central**")
        precios_planta = pd.DataFrame({
            'Bloque Horario': ['Precio Captura', 'Promedio Horario', 'Promedio Solar', 'Promedio Noche'],
            'USD/MWh': [row['CMg precio captura'], row['CMg promedio horario'], row['CMg promedio solar'], row['CMg promedio noche']]
        })
        fig_bar = px.bar(
            precios_planta, 
            x='Bloque Horario', 
            y='USD/MWh', 
            text='USD/MWh',
            template='plotly_white'
        )
        fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)

    # CASO B: VISTA AGREGADA (TODAS LAS CENTRALES)
    else:
        st.subheader(f"📊 Análisis Agregado de Mercado ({ano_sel})")
        
        # KPIs de la muestra filtrada
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Centrales Filtradas", len(df_plot))
        with col2:
            st.metric("CMg Promedio Captura", f"{formato_chileno(df_plot['CMg precio captura'].mean())} USD/MWh")
        with col3:
            st.metric("Inyección a Costo Cero Promedio", f"{formato_chileno(df_plot['Porcentaje iny. costo cero'].mean())} %")
        with col4:
            st.metric("Capacidad Total Filtrada", f"{formato_chileno(df_plot['Potencia máxima bruta Central [MW]'].sum())} MW")

        st.divider()

        # Gráficos de dispersión y distribución
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("**Impacto de la Inyección a Costo Cero**")
            fig1 = px.scatter(
                df_plot, 
                x='Porcentaje iny. costo cero', 
                y='CMg precio captura',
                size='Potencia máxima bruta Central [MW]',
                color='Región' if 'Región' in df_plot.columns else None,
                hover_name='Nombre Central Infotécnica',
                labels={
                    'Porcentaje iny. costo cero': '% Inyección a Costo Cero',
                    'CMg precio captura': 'CMg Precio Captura (USD/MWh)'
                },
                template='plotly_white'
            )
            st.plotly_chart(fig1, use_container_width=True)

        with col_chart2:
            st.markdown("**Distribución de Costos Marginales (USD/MWh)**")
            cmg_cols = ['CMg precio captura', 'CMg promedio horario', 'CMg promedio solar', 'CMg promedio noche']
            df_melted = df_plot.melt(
                id_vars=['Nombre Central Infotécnica'], 
                value_vars=[c for c in cmg_cols if c in df_plot.columns], 
                var_name='Tipo CMg', 
                value_name='USD/MWh'
            )
            fig2 = px.box(
                df_melted, 
                x='Tipo CMg', 
                y='USD/MWh', 
                color='Tipo CMg',
                points="all",
                hover_data=['Nombre Central Infotécnica'],
                template='plotly_white'
            )
            fig2.update_layout(showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

    # --- MÓDULO DE PRE-FACTIBILIDAD BESS ---
st.markdown("---")
st.subheader("🔋 Evaluación de Pre-Factibilidad: Integración BESS")

with st.expander("Ver Análisis de Almacenamiento (Basado en Vertimientos Anuales)"):
    st.info(
        "Este cálculo es un screening de primer nivel. Asume 1 ciclo diario perfecto "
        "y un dimensionamiento de 4 horas para trasladar la energía vertida hacia el bloque nocturno."
    )
    
    # Verificar que existan las columnas necesarias
    if 'Vertimientos [GWh]' in df_plot.columns and 'Spread Día-Noche' in df_plot.columns:
        
        # Crear copia para no alterar el df principal
        df_bess = df_plot.copy()
        
        # Cálculos BESS
        df_bess['BESS_Capacidad_MWh'] = (df_bess['Vertimientos [GWh]'] * 1000) / 365
        df_bess['BESS_Potencia_MW'] = df_bess['BESS_Capacidad_MWh'] / 4
        df_bess['Upside_Económico_Anual_USD'] = df_bess['Vertimientos [GWh]'] * 1000 * df_bess['Spread Día-Noche']
        
        # CASO A: Central Específica
        if central_sel != "Todas":
            row_bess = df_bess.iloc[0]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Potencia BESS Sugerida", f"{formato_chileno(row_bess['BESS_Potencia_MW'])} MW")
            with col2:
                st.metric("Capacidad BESS (4h)", f"{formato_chileno(row_bess['BESS_Capacidad_MWh'])} MWh")
            with col3:
                st.metric("Upside Teórico (Ingreso Extra)", f"$ {formato_chileno(row_bess['Upside_Económico_Anual_USD'])} / año")
                
        # CASO B: Todas las Centrales (Ranking)
        else:
            # Limpiar datos para el ranking (eliminar NaN o infinitos)
            df_bess_clean = df_bess.dropna(subset=['Upside_Económico_Anual_USD', 'BESS_Potencia_MW'])
            
            if not df_bess_clean.empty:
                # Top 10 plantas con mayor potencial económico
                top_bess = df_bess_clean.sort_values(by='Upside_Económico_Anual_USD', ascending=False).head(10)
                
                st.markdown("**Top 10 Centrales con Mayor Potencial para BESS**")
                
                fig_bess = px.bar(
                    top_bess,
                    x='Nombre Central Infotécnica',
                    y='Upside_Económico_Anual_USD',
                    color='BESS_Potencia_MW',
                    labels={
                        'Upside_Económico_Anual_USD': 'Ingreso Teórico (USD/Año)',
                        'BESS_Potencia_MW': 'Tamaño BESS (MW)',
                        'Nombre Central Infotécnica': 'Central'
                    },
                    color_continuous_scale='Viridis',
                    template='plotly_white'
                )
                st.plotly_chart(fig_bess, use_container_width=True)
            else:
                st.warning("No hay suficientes datos válidos para generar el ranking BESS en la selección actual.")
    else:
        st.error("⚠️ Faltan las columnas 'Vertimientos [GWh]' o 'Spread Día-Noche' en la base de datos para realizar este cálculo.")

    # --- TABLA DE DATOS DETALLADA (Aplica a ambos casos) ---
    st.markdown("### Detalle Olas de Datos Filtrados")
    df_mostrar = df_plot.copy()
    
    # Columnas a formatear visualmente
    columnas_a_formatear = columnas_numericas + ['Eficiencia de Captura (%)', 'Spread Día-Noche']
    for col in columnas_a_formatear:
        if col in df_mostrar.columns:
            df_mostrar[col] = df_mostrar[col].apply(lambda x: formato_chileno(x) if pd.notnull(x) else x)
            
    st.dataframe(df_mostrar, use_container_width=True)