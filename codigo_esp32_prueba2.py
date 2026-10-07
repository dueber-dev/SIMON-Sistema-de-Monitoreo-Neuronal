import socket
import csv
import time
import os
from datetime import datetime

# --- CONFIGURACIÓN DE RED ---
TCP_IP = '192.168.4.1'
TCP_PORT = 8080

# --- CREACIÓN AUTOMÁTICA DEL ARCHIVO CSV ---
version = 1
while os.path.exists(f"datos_panel_solar_wifi_v{version}.csv"):
    version += 1
archivo_csv = f"datos_panel_solar_wifi_v{version}.csv"

# Nuevos encabezados para las 6 columnas del INA219
encabezados = ['Segundos', 'V_Panel_V', 'Corriente_mA', 'Potencia_mW', 'Temperatura_C', 'Luz_Pct']

with open(archivo_csv, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(encabezados)

def imprimir_encabezado_consola():
    print("=======================================================================================================")
    print(f" SISTEMA DE MONITOREO WI-FI (INA219) | IP: {TCP_IP}:{TCP_PORT} | ARCHIVO: {archivo_csv}")
    print("=======================================================================================================")
    print(f"{'Hora':<10} {'Tiempo':<8} {'V_Panel':<10} {'Corriente':<12} {'Potencia':<12} {'Temp':<10} {'Luz':<10}")
    print("-" * 103)

imprimir_encabezado_consola()

# --- BUCLE PRINCIPAL DE CONEXIÓN Y LECTURA ---
while True:
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectando al ESP32 por Wi-Fi...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((TCP_IP, TCP_PORT))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Enlace TCP establecido con éxito.\n")
        
        sock.settimeout(None) 
        buffer = ""
        
        while True:
            data = sock.recv(1024)
            if not data:
                break 
                
            buffer += data.decode('utf-8', errors='ignore')
            lineas = buffer.split('\n')
            
            for i in range(len(lineas) - 1):
                linea = lineas[i].strip()
                if not linea:
                    continue
                    
                datos = linea.split(',')
                
                # VALIDACIÓN: Ahora exigimos exactamente 6 datos
                if len(datos) == 6:
                    try:
                        # Desempaquetamos los 6 valores
                        segundos, v_panel, corriente, potencia, temp, luz = datos
                        
                        # Imprimir en consola con formato alineado
                        hora_actual = datetime.now().strftime('%H:%M:%S')
                        print(f"{hora_actual:<10} {segundos+'s':<8} {float(v_panel):>5.2f} V   {float(corriente):>7.1f} mA   {float(potencia):>7.1f} mW   {float(temp):>5.1f} °C   {float(luz):>5.1f} %", flush=True)                        
                        # Guardar en CSV
                        with open(archivo_csv, mode='a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow(datos)
                            
                    except ValueError:
                        pass # Ignora fragmentos dañados por interferencia Wi-Fi
            buffer = lineas[-1]
        
    except (socket.timeout, ConnectionRefusedError, socket.error):
        time.sleep(2) 
    finally:
        sock.close()