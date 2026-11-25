@echo off
REM Demo en vivo: entrena el modelo con todas las sesiones de la nube y abre la dashboard en http://localhost:8790/simon/
cd /d "%~dp0"
python ml\servidor_local.py
pause
