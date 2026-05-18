@echo off

cd /d "%~dp0"

echo ============================================
echo AVVIO SISTEMA AUTONOMO NAO
echo ============================================

set NAO_AUTONOMOUS_LIFE=1
set NAO_PYTHON=C:\Python27\python.exe

echo.
echo AutonomousLife attivo
echo Python NAO: %NAO_PYTHON%
echo.

"%NAO_PYTHON%" scripts\autonomous_watchdog.py

echo.
echo Watchdog terminato.
pause