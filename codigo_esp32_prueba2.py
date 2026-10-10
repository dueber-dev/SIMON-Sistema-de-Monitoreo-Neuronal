"""Cliente TCP del ESP32. Conserva seis columnas y separa reinicios en otro CSV."""
import csv
import math
from pathlib import Path
import socket
import time

TCP_IP = '192.168.4.1'
TCP_PORT = 8080
HEADERS = ['Segundos', 'V_Panel_V', 'Corriente_mA', 'Potencia_mW', 'Temperatura_C', 'Luz_Pct']
MAX_LINE_BYTES = 512


def parse_record(line):
    """Valida todos los campos sin transformar ni corregir las mediciones."""
    values = line.strip().split(',')
    if len(values) != len(HEADERS):
        raise ValueError('Se requieren seis campos')
    numbers = [float(value) for value in values]
    if not all(math.isfinite(value) for value in numbers):
        raise ValueError('La trama contiene valores no finitos')
    if numbers[0] < 0 or not 0 <= numbers[5] <= 100:
        raise ValueError('Tiempo o porcentaje de luz fuera de rango')
    return values


def read_lines(sock):
    """TCP puede fragmentar o agrupar tramas; limita también la cola incompleta."""
    buffer = b''
    while chunk := sock.recv(1024):
        buffer += chunk
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            if len(line) > MAX_LINE_BYTES:
                raise ValueError('Trama demasiado larga')
            try:
                yield line.decode('ascii').strip()
            except UnicodeDecodeError:
                print('Trama descartada: codificación inválida', flush=True)
        if len(buffer) > MAX_LINE_BYTES:
            raise ValueError('Trama sin delimitador o demasiado larga')
    # Una trama sin salto de línea al cerrar la conexión no se guarda.


def new_csv(directory):
    directory = Path(directory)
    version = 1
    while True:
        path = directory / f'datos_panel_solar_wifi_v{version}.csv'
        try:
            file = path.open('x', newline='', encoding='utf-8')
        except FileExistsError:
            version += 1
            continue
        writer = csv.writer(file)
        writer.writerow(HEADERS)
        file.flush()
        return path, file, writer


def record_connection(sock, state, directory):
    for line in read_lines(sock):
        if not line:
            continue
        try:
            values = parse_record(line)
        except ValueError as error:
            print(f'Trama descartada: {error}', flush=True)
            continue
        seconds = float(values[0])
        if state['file'] is None or seconds < state['last_seconds']:
            if state['file'] is not None:
                state['file'].close()
                state['file'] = None
            path, state['file'], state['writer'] = new_csv(directory)
            print(f'Registrando en {path}', flush=True)
        state['writer'].writerow(values)
        state['file'].flush()
        state['last_seconds'] = seconds
        print(','.join(values), flush=True)


def main(directory='.'):
    state = {'file': None, 'writer': None, 'last_seconds': -1}
    try:
        while True:
            try:
                print(f'Conectando a {TCP_IP}:{TCP_PORT}', flush=True)
                with socket.create_connection((TCP_IP, TCP_PORT), timeout=5) as sock:
                    sock.settimeout(10)
                    record_connection(sock, state, directory)
            except (OSError, ValueError) as error:
                print(f'Enlace interrumpido: {error}', flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        print('Registro detenido', flush=True)
    finally:
        if state['file'] is not None:
            state['file'].close()


if __name__ == '__main__':
    main()
