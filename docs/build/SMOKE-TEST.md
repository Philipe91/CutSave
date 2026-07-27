# SMOKE TEST do pacote instalado — roteiro do Philipe (L1)

Valida o PACOTE (instalador + exe), não o código-fonte. Rodar depois de
`build.bat` + `ISCC installer\printnest.iss`, de preferência num PC (ou
usuário do Windows) que nunca teve o PrintNest.

Instalador: `dist_installer\PrintNest-Setup-<versão>.exe`

| # | Passo | OK? |
|---|---|---|
| 1 | Duplo clique no instalador. SmartScreen pode avisar (sem code signing): "Mais informações" → "Executar assim mesmo". | ☐ |
| 2 | Tela de aceite mostra o EULA em português; instala em Program Files; cria atalho no menu iniciar e (se marcado) na área de trabalho. | ☐ |
| 3 | O app abre pelo atalho. Num PC "novo" (sem licença), a tela de ATIVAÇÃO aparece com o ID da Máquina e o campo "Código de compra". | ☐ |
| 4 | Ativar com uma chave de teste (robô rodando). O app abre normal. | ☐ |
| 5 | Importar 1 PDF (Ctrl+I), quantidade 4, clicar **Colocar na chapa**; depois **Gerar Faca**. Preview mostra peças + faca. | ☐ |
| 6 | Exportar PDF de impressão (Ctrl+P) e DXF único — os 2 arquivos abrem (PDF no leitor, DXF no Corel). | ☐ |
| 7 | Salvar projeto (.printnest), fechar o app, reabrir pelo atalho, abrir o projeto: arranjo volta como estava (F2). | ☐ |
| 8 | Menu Ajuda → Tutor IA/README na pasta instalada (`C:\Program Files\PrintNest`): VERSAO.txt com a versão e data da build. | ☐ |
| 9 | Painel de Controle → Programas: "PrintNest Premium" listado com versão; desinstalar remove o programa MAS uma reinstalação volta ATIVADA (a licença em %APPDATA%\PrintNest sobrevive). | ☐ |
| 10 | Pasta "Plugin CorelDRAW" instalada junto; `instalar_plugin_corel.bat` presente. | ☐ |

Qualquer ☐ que falhar: anotar o número + o que apareceu na tela e me mandar.
