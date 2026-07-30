PrintNest - Preparacao de Producao Grafica
============================================

O QUE E
-------
Software para preparar arquivos de producao: importar PDFs, gerar faca,
aplicar offset/recorte, organizar o nesting e exportar o PDF de impressao
e o DXF de corte.


REQUISITOS MINIMOS
------------------
- Windows 10 ou 11 (64 bits)
- ~200 MB livres em disco
- NAO precisa de Python instalado (ja vem embarcado no executavel)


COMO INSTALAR
-------------
Com o INSTALADOR (recomendado): duplo clique em
PrintNest-Setup-<versao>.exe, aceite o contrato e avance. O programa
fica no menu Iniciar (e na Area de Trabalho, se voce marcar a opcao).

Sem instalador (pasta avulsa): copiar a pasta "PrintNest_Build" para
qualquer lugar do computador tambem funciona.


COMO EXECUTAR
-------------
1. Abra o PrintNest pelo atalho do menu Iniciar (ou, na pasta avulsa,
   duplo clique em PrintNest.exe).
   (Na primeira vez o Windows pode levar alguns segundos para abrir,
    porque o executavel se descompacta - isso e normal.)
2. Se o Windows SmartScreen avisar ("aplicativo nao reconhecido"),
   clique em "Mais informacoes" > "Executar assim mesmo".


FLUXO BASICO
------------
1. Adicionar PDFs.
2. Ajustar a coluna Qtd (quantas copias de cada arquivo).
3. Definir largura/altura da chapa, espacamento, offset, recorte.
4. Escolher o tipo de registro, se usar (Nenhuma / Circulos / Marcas em L /
   Circulos + L / Quadrados / Cruzes / L de canto).
5. Clicar em "Colocar na chapa" (ou F5) e conferir o preview
   (roda do mouse = zoom, arrastar = mover).
6. Exportar PDF (impressao) e DXF (corte).


ONDE FICAM AS CONFIGURACOES
---------------------------
As preferencias (ultimo material, offset, etc.) e os logs ficam em:

   %APPDATA%\PrintNest

   (cole esse caminho no Explorador de Arquivos para abrir)

Apagar essa pasta apenas reseta as configuracoes; nao afeta o programa.


OBSERVACOES
-----------
- O arquivo de CORTE (DXF) deve ser validado na mesa de corte
  (iBrightCut / Mimaki) antes do uso em larga escala.


PARA O DESENVOLVEDOR - COMO GERAR O PACOTE (2 passos)
-----------------------------------------------------
1. build.bat
   -> PyInstaller monta PrintNest_Build\ (exe + Tutor IA + plugin Corel)
2. "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\printnest.iss
   -> gera dist_installer\PrintNest-Setup-<versao>.exe
Versao: alinhar app/__init__.py, docs/build/VERSAO.txt e o MyAppVersion
do installer/printnest.iss. Depois: smoke test (docs/build/SMOKE-TEST.md).
