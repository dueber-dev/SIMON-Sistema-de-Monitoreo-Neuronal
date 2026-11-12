
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import time
import urllib.request
from datetime import datetime

st.set_page_config(page_title="Monitor Solar ESP32 (INA219)", page_icon="☀️", layout="wide")

FOTOS_DIR = "fotos_panel_simon"
os.makedirs(FOTOS_DIR, exist_ok=True)

def obtener_fotos_guardadas():
    fotos = glob.glob(os.path.join(FOTOS_DIR, "*.jpg"))
    if fotos:
        fotos.sort(key=os.path.getctime, reverse=True)
    return fotos

def capturar_foto_manual(ip):
    try:
        url_captura = f"http://{ip}/capture"
        req = urllib.request.Request(url_captura, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            foto_bytes = resp.read()
            if foto_bytes and len(foto_bytes) > 1000:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                nombre = f"foto_{ts}.jpg"
                ruta = os.path.join(FOTOS_DIR, nombre)
                with open(ruta, "wb") as f:
                    f.write(foto_bytes)
                return True, nombre
    except Exception as e:
        return False, str(e)
    return False, "Error desconocido"

def obtener_lista_csv():
    archivos_csv = glob.glob("datos_panel_solar_wifi_v*.csv")
    if archivos_csv:
        archivos_csv.sort(key=os.path.getctime, reverse=True)
    return archivos_csv

st.sidebar.header("⚙ Configuración del Panel")
potencia_nominal_w = st.sidebar.number_input("Potencia Nominal (W)", min_value=0.1, max_value=50.0, value=1.0, step=0.1)

st.sidebar.markdown("---")
st.sidebar.header("📷 Cámara ESP32-CAM")
mostrar_camara = st.sidebar.checkbox("Activar vista de cámara", value=True)
ip_cam = st.sidebar.text_input("IP de la cámara", value="192.168.4.2")
puerto_cam = st.sidebar.number_input("Puerto del Stream", min_value=1, max_value=65535, value=81)
ruta_cam = st.sidebar.text_input("Ruta", value="/stream")
url_stream = f"http://{ip_cam}:{puerto_cam}{ruta_cam}"

st.title("☀️ Dashboard de Monitoreo: Panel Solar")
st.markdown("Adquisición de datos en tiempo real de alta precisión (INA219 I2C).")

if mostrar_camara:
    with st.expander("📷 Cámara de Inspección en Vivo (ESP32-CAM)", expanded=True):
        c_cam, c_desc = st.columns([2, 1])
        with c_cam:
            st.markdown(
                f"""
                <div style="background:#0e1117; padding:6px; border-radius:8px; text-align:center;">
                    <img src="{url_stream}" style="max-width:100%; height:auto; border-radius:6px; min-height:180px; background:#1e1e1e;"
                         alt="Cámara ESP32-CAM"
                         onerror="this.onerror=null; this.src=''; this.parentElement.innerHTML='<div style=\\\'color:#ff6b6b;padding:24px;font-family:sans-serif;\\\'>⚠️ No se detecta transmisión en <code>{url_stream}</code>.<br><small style=\\\'color:#aaa;\\\'>Asegúrate de que la ESP32-CAM esté encendida y en la misma red Wi-Fi.</small></div>';" />
                </div>
                """,
                unsafe_allow_html=True
            )
        with c_desc:
            st.markdown(f"**URL:** `{url_stream}`")
            st.markdown("**Ubicación:** Soporte impreso en 3D (50°)")
            st.markdown("**Propósito:** Detección visual de suciedad, polvo o sombreado.")
            st.caption("El soporte se inclina junto al panel sin proyectar sombra sobre las celdas.")

            if st.button("📸 Capturar y guardar foto ahora"):
                ok, res = capturar_foto_manual(ip_cam)
                if ok:
                    st.success(f"Guardada: `{res}` en `{FOTOS_DIR}/`")
                else:
                    st.error(f"Error al capturar: {res}")

        # Galería de fotos guardadas
        fotos_guardadas = obtener_fotos_guardadas()
        if fotos_guardadas:
            st.markdown(f"**📂 Fotos almacenadas en `{FOTOS_DIR}/`:** {len(fotos_guardadas)} foto(s)")
            foto_elegida = st.selectbox("Selecciona una foto para verla:", fotos_guardadas, format_func=lambda x: os.path.basename(x))
            st.image(foto_elegida, caption=f"Foto: {os.path.basename(foto_elegida)}", use_container_width=True)

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