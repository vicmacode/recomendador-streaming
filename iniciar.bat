@echo off
title Recomendador de Streaming
cd /d "%~dp0"
cls

echo  ==========================================
echo    Recomendador de Contenido - Streaming
echo    1ACC0184  Complejidad Algoritmica - UPC
echo  ==========================================
echo.

echo  Verificando dependencias...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo  ERROR: No se pudo instalar Flask.
    echo  Verifica tu conexion a internet e intenta de nuevo.
    pause
    exit /b 1
)

echo  Iniciando servidor...
start /b python servidor.py

timeout /t 3 /nobreak > nul
echo.
echo  Servidor activo en: http://localhost:5000
echo.
echo  Presiona cualquier tecla para APAGAR el servidor...
echo  ==========================================
pause > nul

echo.
echo  Apagando servidor...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 " 2^>nul') do (
    taskkill /f /pid %%a > nul 2>&1
)
echo  Servidor apagado. Hasta luego.
timeout /t 2 /nobreak > nul
