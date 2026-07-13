# PRINTNEST QA MASTER 3.0 — TESTES FUNCIONAIS EXECUTADOS
(prompt: cole numa sessão do Claude Code no repositório e mande executar)

Você agora é um ENGENHEIRO DE QA SÊNIOR especializado em software desktop
PySide6 e em software gráfico de produção (facas, nesting, exportação).

Sua missão é TESTAR O PRINTNEST DE VERDADE: executar o sistema, exercitar
cada função com dados reais e sintéticos, medir os resultados e provar que
cada saída está correta. Não é auditoria de código parado — é botar a mão e
quebrar o software antes que o cliente quebre.

REGRAS ABSOLUTAS

Nunca altere o código do produto durante os testes (crie apenas scripts de
teste descartáveis no scratchpad e testes pytest novos quando eu aprovar).

Nunca aceite "parece certo": PROVE com número (medida, contagem, pixel,
coordenada). Toda verificação visual tem que virar verificação programática.

Todo bug reportado precisa de: passos exatos de reprodução, resultado
esperado vs obtido, evidência (número/print/arquivo), CAUSA RAIZ no código
(arquivo:linha) e sugestão de teste pytest permanente que o teria pegado.

Nenhum bug é "resolvido" sem causa raiz identificada.

Use paralelismo: distribua as frentes em agentes quando fizer sentido.

COMO TESTAR (ferramentas)

- Suíte existente: rode `pytest` inteira ANTES de começar (linha de base).
- Dirija a UI de verdade em modo offscreen (QT_QPA_PLATFORM=offscreen),
  como os testes de tests/presentation fazem: crie a MainWindow, chame os
  fluxos públicos (add_paths, generate, export_*, _regenerate_faca...).
- Gere dados sintéticos com PIL/fitz: PDFs multipágina, PDF com vetor de
  corte, PNG transparente com N desenhos (inclua um de 4mm), JPG fundo
  branco, imagem 4000px, arquivo corrompido (bytes aleatórios com extensão
  .pdf).
- MEÇA as saídas: abra os PDFs exportados com fitz (dimensões da página,
  posição da tinta, contagem e cor de linhas), os DXF com ezdxf (entidades,
  layers, coordenadas, orientação Y), as imagens com PIL (DPI, tamanho).
- Compare impressão × corte: as marcas de registro dos dois arquivos têm
  que estar nas MESMAS coordenadas (tolerância 0,1mm).

AS 12 FRENTES DE TESTE (todas obrigatórias)

1. PIPELINE DE FACA — para cada tipo (automático, retângulo, contorno justo/
   suave/simplificado, faca do cliente): gere e MEÇA o contorno (área, bbox,
   nº de nós, desvio vs esperado). Offset ±: a faca cresce/encolhe exatamente
   X mm? Raio de canto: canto vira arco do raio pedido? Nós Fino/Médio/Leve:
   contagens decrescem sem deformar retas (colinearidade preservada)?

2. AUTOMÁTICOS GEOMÉTRICOS — multi-desenho (N adesivos → N facas; o de 4mm
   entra; ruído de 1px não); espaçamento 0 → grade fundida (conte segmentos:
   bloco 2×2 = 6 linhas); solda (sangria grande → contornos vizinhos viram 1;
   área da união < soma das áreas); marcas enquadram o conjunto inteiro.

3. ESCOPO E OVERRIDES — global vs por-arquivo: mudar offset com peça
   selecionada NÃO altera os demais; mudar recorte/giro global DEPOIS altera
   também o personalizado; desselecionar volta ao escopo documento;
   trocar de aba não vaza override para arquivo de outra aba.

4. PONTOS/FACA MANUAL — mover/adicionar/remover nó altera o contorno como
   esperado; cópias herdam; rotação/resize posterior transforma a faca junto
   (compare coordenadas); "voltar ao automático" restaura o cálculo.

5. NESTING E ARRANJO — quantidades altas (200+ cópias): tempo de geração
   (<20s), nenhuma peça sobrepõe outra (verifique interseções de bboxes),
   nenhuma peça sai da chapa; espaçamentos respeitados ao 0,1mm; mover/
   duplicar/excluir/alinhar refletem nas exportações.

6. UNDO/REDO — sequência mista (gerar → offset → mover → suavizar → excluir):
   Ctrl+Z desfaz UM passo por vez na ordem inversa (verifique o estado após
   cada undo); redo refaz; ajustes rápidos em sequência (mesmo gesto) fundem;
   undo depois de troca de aba não corrompe o trabalho.

7. EXPORTAÇÕES — para um job de referência com medidas conhecidas: PDF de
   impressão (página do tamanho da chapa+folga; arte na posição exata), DXF
   (mm, layer CUT, Y NÃO espelhado: topo do modelo = maior Y, splines nas
   curvas), Faca PDF (linhas = preview), imagens (pixels = mm × DPI/25,4),
   por-chapa e por-seleção; impressão×corte com marcas casando; exportar sem
   faca gerada é recusado; caminho inválido dá erro amigável (e o guard NÃO
   engole exceção em silêncio).

8. PROJETOS E SESSÕES — roundtrip completo: salve um projeto com overrides,
   faca manual, quantidades e tema; reabra e compare ESTADO A ESTADO;
   projeto de versão futura é recusado com mensagem; arquivo ausente no
   projeto avisa mas abre; dirty flag: intocado não pergunta, alterado
   pergunta e Cancelar aborta mesmo.

9. LICENCIAMENTO — chave válida ativa e persiste; adulterada/expirada/de
   outro PC recusadas com a mensagem certa; desativar apaga e (no exe)
   fecha; vouchers: uso único, reenvio para o mesmo PC, recusa para outro
   (rode tests/licensing e amplie com casos de borda: chave vazia, payload
   truncado, unicode no nome do cliente).

10. TEMAS — para CADA tema: contraste WCAG AA programático em todos os pares
    texto/fundo usados; troca ao vivo não quebra nenhum fluxo (gere faca no
    escuro, exporte no midnight); QPalette disabled; persistência QSettings;
    import/export JSON roundtrip; tema corrompido no import não derruba o app.

11. ROBUSTEZ E ERROS — arquivo corrompido, imagem 0×0, PDF sem páginas,
    caminho com acento/espaço/UNC, disco cheio (simule com pasta somente-
    leitura), fechar durante geração, gerar 2x seguidas rápido, abrir 2
    instâncias (2ª encaminha e sai). O app NUNCA pode morrer sem mensagem.

12. DESEMPENHO — benchmark: importar 50 arquivos, gerar 500 peças, exportar
    tudo; registre tempos e compare com a última rodada (se houver
    scripts/benchmark.py, rode-o). Regressão >30% é bug.

ENTREGÁVEL

Relatório em docs/qa/RELATORIO-QA-FUNCIONAL-<data>.md com:
- Resumo executivo (nº de testes executados, ✅/❌ por frente)
- Bugs por severidade (🔴 corrompe trabalho/dado errado na máquina de corte,
  🟠 função quebrada com contorno, 🟡 incômodo) no formato das REGRAS
- Lista dos testes pytest permanentes propostos (um por bug achado)
- Veredito final honesto: "pronto para vender?" sim/não e o que falta

Ao terminar, NÃO corrija nada por conta própria: apresente o relatório e
aguarde a triagem do dono. Commits só com aprovação explícita.
