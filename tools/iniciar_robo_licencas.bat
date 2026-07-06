@echo off
rem Robo de ativacao do PrintNest — deixe esta janela aberta.
cd /d "%~dp0.."
.venv\Scripts\python.exe -u tools\license_robot.py
pause
