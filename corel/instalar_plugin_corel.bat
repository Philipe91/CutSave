@echo off
chcp 65001 >nul
title Instalador do plugin PrintNest para CorelDRAW
echo.
echo  =====================================================
echo    PrintNest - Instalador do plugin para CorelDRAW
echo  =====================================================
echo.

set "ORIGEM=%~dp0"
set "ACHOU=0"

if not exist "%ORIGEM%PrintNest.gms" goto SEM_GMS

rem Procura TODAS as versoes do CorelDRAW do usuario e instala em cada uma.
rem A pasta GMS e carregada automaticamente pelo Corel ao abrir (GlobalMacros).
for /d %%C in ("%APPDATA%\Corel\*") do (
  if exist "%%C\Draw\GMS\" (
    copy /y "%ORIGEM%PrintNest.gms" "%%C\Draw\GMS\" >nul
    echo   [OK] Plugin instalado em: %%~nxC
    set "ACHOU=1"
  )
)

if "%ACHOU%"=="0" (
  echo   [!] Nenhum CorelDRAW encontrado neste usuario.
  echo       Abra o CorelDRAW UMA vez e rode este instalador de novo.
  echo.
  pause
  exit /b 1
)

echo.
echo  -----------------------------------------------------
echo   Plugin instalado! Falta so criar o botao na barra:
echo.
echo   1. Abra o PrintNest UMA vez (ele se registra sozinho)
echo   2. Abra o CorelDRAW
echo   3. Ferramentas ^> Opcoes ^> Personalizacao ^> Comandos
echo   4. No filtro, escolha "Macros"
echo   5. Arraste "PrintNest.EnviarParaPrintNest" para a barra
echo   6. (Opcional) Na aba Aparencia, importe a imagem
echo      printnest_symbol.png que esta nesta pasta
echo.
echo   Pronto: desenhou, clicou, caiu no PrintNest.
echo  -----------------------------------------------------
echo.
pause
exit /b 0

:SEM_GMS
echo   [!] Arquivo PrintNest.gms nao encontrado nesta pasta.
echo.
echo   Instalacao manual (2 minutos): abra o CorelDRAW, pressione
echo   Alt+F11, clique com o botao direito em "GlobalMacros" ^>
echo   Import File... e escolha o PrintNest.bas desta pasta.
echo   Depois siga o GUIA-CLIENTE para criar o botao.
echo.
pause
exit /b 1
