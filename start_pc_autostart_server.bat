@echo off

cd /d "%~dp0"

echo ============================================
echo SERVER AUTOSTART NAO
echo ============================================

set NAO_AUTONOMOUS_LIFE=1
set NAO_PYTHON=C:\Python27\python.exe

echo.
echo Server PC in ascolto per bootstrap NAO
echo Python NAO: %NAO_PYTHON%
echo.

"%NAO_PYTHON%" scripts\pc_autostart_server.py

echo.
echo Server autostart terminato.
pause