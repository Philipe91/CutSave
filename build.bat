@echo off
REM ============================================================
REM  PrintNest - build Windows (PyInstaller, executavel unico)
REM  Uso: clique duplo neste arquivo, ou rode "build.bat" no terminal.
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/4] Gerando icone...
".venv\Scripts\python.exe" assets\make_icon.py

echo [2/4] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Empacotando com PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm --onefile --windowed ^
  --name PrintNest ^
  --icon assets\printnest.ico ^
  printnest_main.py

echo [4/4] Montando pasta PrintNest_Build...
if exist PrintNest_Build rmdir /s /q PrintNest_Build
mkdir PrintNest_Build
copy /y dist\PrintNest.exe PrintNest_Build\PrintNest.exe
if exist README_BUILD.txt copy /y README_BUILD.txt PrintNest_Build\README.txt
if exist VERSAO.txt copy /y VERSAO.txt PrintNest_Build\VERSAO.txt

echo.
echo Build concluida em: PrintNest_Build\PrintNest.exe
endlocal
