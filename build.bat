@echo off
REM ============================================================
REM  PrintNest - build Windows (PyInstaller, executavel unico)
REM  Uso: clique duplo neste arquivo, ou rode "build.bat" no terminal.
REM  A configuracao da build fica em PrintNest.spec (fonte unica).
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/4] Gerando icone e tela de abertura...
".venv\Scripts\python.exe" assets\make_icon.py
".venv\Scripts\python.exe" assets\make_splash.py

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
if exist "docs\build\BUILD.md" copy /y "docs\build\BUILD.md" PrintNest_Build\README.txt
if exist "docs\build\VERSAO.txt" copy /y "docs\build\VERSAO.txt" PrintNest_Build\VERSAO.txt
REM manual "Tutor IA": o cliente joga este PDF na IA preferida (ChatGPT,
REM Claude, Gemini...) e ela vira um tutor do PrintNest que tira duvidas
".venv\Scripts\python.exe" tools\make_tutor_pdf.py "PrintNest_Build\Tutor IA - PrintNest.pdf"
REM LEIA-ME do cliente: e ele que explica o SmartScreen e lista o conteudo da
REM pasta. Ficava de fora, e o cliente abria a pasta sem porta de entrada.
copy /y docs\cliente\LEIA-ME.txt PrintNest_Build\LEIA-ME.txt >nul
REM pacote do plugin CorelDRAW (instalador + macro + guia + icone do botao)
mkdir "PrintNest_Build\Plugin CorelDRAW"
copy /y corel\instalar_plugin_corel.bat "PrintNest_Build\Plugin CorelDRAW\" >nul
copy /y corel\PrintNest.bas "PrintNest_Build\Plugin CorelDRAW\" >nul
if exist corel\PrintNest.gms copy /y corel\PrintNest.gms "PrintNest_Build\Plugin CorelDRAW\" >nul
copy /y corel\GUIA-CLIENTE.md "PrintNest_Build\Plugin CorelDRAW\GUIA-CLIENTE.txt" >nul
REM guia ILUSTRADO de instalacao do plugin (PDF). O LEIA-ME promete este
REM arquivo ao cliente e ele nunca era copiado: quem usa Corel recebia so o
REM texto, sem as imagens do passo a passo.
copy /y docs\cliente\PLUGIN-CORELDRAW.pdf "PrintNest_Build\Plugin CorelDRAW\" >nul
copy /y assets\printnest_symbol.png "PrintNest_Build\Plugin CorelDRAW\" >nul
REM carimba a data/hora REAL desta build no VERSAO.txt (identifica cada exe)
echo.>> PrintNest_Build\VERSAO.txt
echo Build gerada em: %DATE% %TIME%>> PrintNest_Build\VERSAO.txt

echo.
echo Build concluida em: PrintNest_Build\PrintNest.exe
echo (Opcional) valide com: PrintNest_Build\PrintNest.exe --selftest
endlocal
