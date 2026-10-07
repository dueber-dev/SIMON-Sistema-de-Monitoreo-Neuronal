
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import time

st.set_page_config(page_title="Monitor Solar ESP32 (INA219)", page_icon="☀️", layout="wide")

def obtener_lista_csv():
    archivos_csv = glob.glob("datos_panel_solar_wifi_v*.csv")
    if archivos_csv:
        archivos_csv.sort(key=os.path.getctime, reverse=True)
    return archivos_csv

st.sidebar.header("⚙ Configuración del Panel")
potencia_nominal_w = st.sidebar.number_input("Potencia Nominal (W)", min_value=0.1, max_value=50.0, value=1.0, step=0.1)

st.title("☀️ Dashboard de Monitoreo: Panel Solar")
st.markdown("Adquisición de datos en tiempo real de alta precisión (INA219 I2C).")

archivos = obtener_lista_csv()

if not archivos:
    st.warning("⏳ Esperando datos... Inicia tu script TCP.")
    time.sleep(2)
    st.rerun()
else:
    st.sidebar.markdown("---")
    archivo_actual = st.sidebar.selectbox("📂 Seleccionar historial:", archivos)
    
    try:
        # Forzamos los nombres de las columnas que vienen del nuevo código C++
        nombres_columnas = ['Segundos', 'V_Panel_V', 'Corriente_mA', 'Potencia_mW', 'Temperatura_C', 'Luz_Pct']
        df = pd.read_csv(archivo_actual, names=nombres_columnas, header=None)
        
        # Ignoramos la primera fila si contiene texto en lugar de números
        df = df[pd.to_numeric(df['Segundos'], errors='coerce').notnull()]
        df = df.astype(float)
        
        if len(df) > 0:
            ultimo_dato = df.iloc[-1]
            potencia_actual_w = ultimo_dato['Potencia_mW'] / 1000.0
            
            if potencia_actual_w == 0.0:
                st.error("🚨 **ALERTA:** Potencia 0.0 W. Falta de irradiación o circuito abierto.")

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Voltaje", f"{ultimo_dato['V_Panel_V']:.2f} V")
            col2.metric("Corriente", f"{ultimo_dato['Corriente_mA']:.1f} mA")
            col3.metric("Potencia", f"{ultimo_dato['Potencia_mW']:.1f} mW")
            col4.metric("Temperatura", f"{ultimo_dato['Temperatura_C']:.1f} °C")
            col5.metric("Irradiancia", f"{ultimo_dato['Luz_Pct']:.1f} %")

            st.markdown("---")
            eje_x = df.index if df['Segundos'].sum() == 0 else 'Segundos'

            g1, g2 = st.columns(2)
            with g1:
                st.plotly_chart(px.line(df, x=eje_x, y='Potencia_mW', title="Potencia (mW)", markers=True), use_container_width=True)
                st.plotly_chart(px.line(df, x=eje_x, y=['V_Panel_V', 'Corriente_mA'], title="Voltaje (V) y Corriente (mA)"), use_container_width=True)
            with g2:
                st.plotly_chart(px.line(df, x=eje_x, y='Luz_Pct', title="Irradiancia (%)"), use_container_width=True)
                st.plotly_chart(px.line(df, x=eje_x, y='Temperatura_C', title="Temperatura (°C)"), use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando el archivo CSV: {e}")

    time.sleep(2)
    st.rerun()

# streamlit run dashboard.py                