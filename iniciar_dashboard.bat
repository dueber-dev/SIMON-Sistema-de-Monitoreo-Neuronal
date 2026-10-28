@echo off
REM Arranca todo de un solo: el receptor TCP (guarda el CSV) y el dashboard de Streamlit.
REM Antes: conecta la laptop a la red Wi-Fi "ESP32_Panel_Solar".
cd /d "%~dp0"
start "SIMON - receptor TCP" python codigo_esp32_prueba2.py
python -m streamlit run dashboard.py
