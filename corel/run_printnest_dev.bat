@echo off
REM ============================================================
REM  Atalho de TESTE (desenvolvimento) para a macro do CorelDRAW.
REM  Roda o PrintNest direto do codigo (sem precisar buildar o .exe).
REM  Na macro PrintNest.bas, aponte PRINTNEST_EXE para o caminho
REM  COMPLETO deste arquivo .bat.
REM
REM  Em producao, use o PrintNest.exe gerado pelo build.bat.
REM ============================================================
REM python.exe (nao pythonw) + log: erro de partida fica gravado em vez de
REM morrer mudo. O console fica oculto porque a macro dispara com vbHide.
"c:\projetos\Cutph\.venv\Scripts\python.exe" "c:\projetos\Cutph\printnest_main.py" %* >> "%TEMP%\printnest_dev.log" 2>&1
