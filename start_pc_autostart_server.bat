@echo off

cd /d "%~dp0"

echo ============================================
echo SERVER AUTOSTART NAO
echo ============================================

set NAO_AUTONOMOUS_LIFE=1
set CHOREGRAPHE_BOOT=1
set SKIP_AUTONOMOUS_LIFE_CONFIG=1
set NAO_PYTHON=C:\Python27\python.exe
set NAO_ROBOT_IP=172.16.165.86
set NAO_ROBOT_PORT=9559

echo.
echo Server PC in ascolto per bootstrap NAO
echo Python NAO: %NAO_PYTHON%
echo Robot NAO: %NAO_ROBOT_IP%:%NAO_ROBOT_PORT%
echo.

"%NAO_PYTHON%" scripts\pc_autostart_server.py

echo.
echo Server autostart terminato.
pause
