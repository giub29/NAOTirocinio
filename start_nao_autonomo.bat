@echo off

cd /d "%~dp0"

echo ============================================
echo AVVIO SISTEMA AUTONOMO NAO
echo ============================================

set NAO_AUTONOMOUS_LIFE=1
set CHOREGRAPHE_BOOT=1
set SKIP_AUTONOMOUS_LIFE_CONFIG=1
set NAO_PYTHON=C:\Python27\python.exe

echo.
echo AutonomousLife attivo
echo Modalita boot autonoma: input tastiera disabilitato
echo Python NAO: %NAO_PYTHON%
echo.

"%NAO_PYTHON%" scripts\autonomous_watchdog.py

echo.
echo Watchdog terminato.
pause
