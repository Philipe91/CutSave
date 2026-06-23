@echo off
REM ============================================================
REM  PrintNest - limpa os artefatos de build (nao toca no codigo)
REM  Remove: build\, dist\, PrintNest_Build\ e caches do PyInstaller.
REM  Mantem: PrintNest.spec, build.bat, assets e o codigo-fonte.
REM ============================================================
setlocal
cd /d "%~dp0"

echo Limpando artefatos de build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist PrintNest_Build rmdir /s /q PrintNest_Build

echo Limpo. (PrintNest.spec e build.bat preservados)
endlocal
