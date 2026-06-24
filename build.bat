@echo off
REM ============================================================
REM  PrintNest - build Windows (PyInstaller, executavel unico)
REM  Uso: clique duplo neste arquivo, ou rode "build.bat" no terminal.
REM  A configuracao da build fica em PrintNest.spec (fonte unica).
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/4] Gerando icone...
".venv\Scripts\python.exe" assets\make_icon.py

echo [2/4] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Empacotando com PyInstaller (PrintNest.spec)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm PrintNest.spec
if errorlevel 1 (
  echo.
  echo ERRO: a build falhou. Verifique as mensagens acima.
  endlocal & exit /b 1
)

echo [4/4] Montando pasta PrintNest_Build...
if exist PrintNest_Build rmdir /s /q PrintNest_Build
mkdir PrintNest_Build
copy /y dist\PrintNest.exe PrintNest_Build\PrintNest.exe
if exist "DOCUMENTAÇÃO\README_BUILD.txt" copy /y "DOCUMENTAÇÃO\README_BUILD.txt" PrintNest_Build\README.txt
if exist "DOCUMENTAÇÃO\VERSAO.txt" copy /y "DOCUMENTAÇÃO\VERSAO.txt" PrintNest_Build\VERSAO.txt

echo.
echo Build concluida em: PrintNest_Build\PrintNest.exe
echo (Opcional) valide com: PrintNest_Build\PrintNest.exe --selftest
endlocal
