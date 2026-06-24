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
Nao precisa instalador. Basta copiar a pasta "PrintNest_Build" para
qualquer lugar do computador (ex.: Area de Trabalho ou C:\PrintNest).


COMO EXECUTAR
-------------
1. Abra a pasta PrintNest_Build.
2. Du-plo clique em PrintNest.exe.
   (Na primeira vez o Windows pode levar alguns segundos para abrir,
    porque o executavel se descompacta - isso e normal.)
3. Se o Windows SmartScreen avisar ("aplicativo nao reconhecido"),
   clique em "Mais informacoes" > "Executar assim mesmo".


FLUXO BASICO
------------
1. Adicionar PDFs.
2. Ajustar a coluna Qtd (quantas copias de cada arquivo).
3. Definir largura/altura da chapa, espacamento, offset, recorte.
4. Escolher o tipo de registro (Nenhum / Bolinhas / Mimaki), se usar.
5. Clicar em "Gerar Producao" e conferir o preview
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
- Esta e uma versao prototipo para testes reais na producao.
- O arquivo de CORTE (DXF) deve ser validado na mesa de corte
  (iBrightCut / Mimaki) antes do uso em larga escala.
