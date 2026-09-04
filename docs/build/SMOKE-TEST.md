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

---

## Cor (a partir da 1.2.0)

O defeito que a 1.2.0 corrige é de COR, e ele só aparece em arquivo CMYK real —
os PDFs de exemplo são RGB e passam mesmo com o bug presente. Use uma arte
CMYK sua.

| # | Passo | OK? |
|---|---|---|
| 11 | Importar uma arte **CMYK** (JPEG fechado pela gráfica serve), montar a chapa e exportar **PDF**. Abrir no Acrobat → Produção de impressão → **Visualização de saída**: as separações aparecem em **CMYK**, não em RGB. | ☐ |
| 12 | Na mesma janela, desligar os canais M, Y e K: um ciano de 100% da arte continua inteiro (ele está só no ciano). Se ele aparecer também nos outros canais, a cor foi convertida — falhou. | ☐ |
| 13 | Ainda na Visualização de saída, isolar o canal **K**: as marcas de registro aparecem só nele. | ☐ |
| 14 | **Ctrl+E** → formato "Imagem (PNG / JPG)": aparecem **Espaço de cor**, **Perfil** e **Qualidade (JPEG)**, cada um em sua linha, sem campos sobrepostos. Escolher CMYK mostra a linha do Perfil com um perfil do Windows já selecionado. | ☐ |
| 15 | Exportar em JPEG com CMYK. O arquivo abre no Corel/Photoshop **como CMYK**, com perfil embutido. (Lembrete: essa imagem é conversão, não a tinta original — para impressão, vale o PDF do passo 11.) | ☐ |

## Upgrade por cima (obrigatório antes de atualizar PC de cliente)

| # | Passo | OK? |
|---|---|---|
| 16 | Num PC que já tenha a versão anterior **ativada**, instalar a nova por cima sem desinstalar. O app abre **já ativado** — não pede código de novo. | ☐ |
| 17 | As configurações continuam como estavam (DPI de exportação, tipo de marca de registro, unidade). | ☐ |
| 18 | "Sobre" mostra a versão nova. | ☐ |

Se o 16 falhar, **pare**: não atualize mais nenhum PC de cliente até entender o
motivo — o cliente fica travado sem conseguir trabalhar.
