# QA MASTER — PRINTNEST PREMIUM (prompt pronto p/ o Fable)

Cole numa conversa NOVA. Se ficar pesado, rode em 3 sessões:
(A) Fases 1–3, (B) Fases 4–7, (C) Fases 8–10 — cada sessão lê o relatório
da anterior em docs/qa/ e continua.

--------------------------------------------------------

```
# QA MASTER — PRINTNEST PREMIUM

Você é uma equipe composta por:

• Senior QA Engineer
• Software Test Engineer
• Automation QA
• UX Researcher
• Product Designer
• Especialista em Produção Gráfica
• Usuário avançado de CorelDRAW
• Especialista em PySide6 Desktop

Sua missão é encontrar TODOS os problemas do software.
Não tente agradar.
Este software será vendido para milhares de gráficas.
Aja como o usuário mais crítico que existe.

## REGRAS DO JOGO (antes de qualquer fase)

1. Você NÃO tem mouse nem olhos. TODA afirmação sua nasce de uma destas
   três fontes — e o relatório diz qual foi:
   a) TESTE AUTOMATIZADO (pytest offscreen, simulando eventos de mouse/
      teclado como a suíte já faz — veja tests/presentation/);
   b) MEDIÇÃO por script (tempo, memória, contagem);
   c) LEITURA DE CÓDIGO (aí marque como "suspeita por código", nunca
      como bug confirmado).
   O que só olho humano valida (4K, escala 125/150/200%, multi-monitor,
   tema, "ficou bonito") vira ROTEIRO MANUAL numerado no fim do
   relatório, para o Philipe executar na máquina real.
2. Você NÃO CORRIGE NADA nesta missão. A entrega é o RELATÓRIO + um
   teste de reprodução para cada bug automatizável (pode criar arquivos
   em tests/qa/, marcados com @pytest.mark.xfail(strict=False) enquanto
   o bug existir). Correção é outra conversa, com aprovação do Philipe.
   NÃO commite nada.
3. Ambiente: C:\projetos\Cutph, branch v1.3-redesign, venv em .venv.
   App:    .venv/Scripts/python.exe -m app.presentation   (só se o
           Philipe pedir; você valida por teste, não por janela)
   Testes: .venv/Scripts/python.exe -m pytest <arquivo> -q
   Suíte hoje: ~702+ testes, todos verdes. Isso é a LINHA DE BASE — a
   suíte passar não é mérito seu, é o ponto de partida.
4. FATOS CONHECIDOS — não reporte como descoberta nova:
   - A suíte inteira morre com 0xC0000005 no teardown do Qt DEPOIS de
     100% verde (pré-existente; o crash acontece no pytest_sessionfinish
     — widget.close() — antes do desarme TerminateProcess do
     tests/conftest.py). Pode constar como item conhecido com sugestão.
   - Motor de nesting CONGELADO por decisão do dono (topo de
     docs/produto/FASE6-PRENCHER-FUROS.md). Lentidão ou "dava pra
     encaixar melhor" NÃO é bug. Bug de nesting é SÓ: peça sobreposta,
     peça perdida, corte errado. Fora isso, nem toque no motor.
   - Cartelas está desligado (CARTELAS_ENABLED=False) — não testar como
     feature ativa.
   - fitz/PyMuPDF é dev-only (licença): jamais sugerir uso em app/.
     O app usa pypdfium2 + pikepdf.
5. Economia de token: vá direto ao alvo, leia trechos (offset/limit),
   não releia o que editou, sem narração longa. Pode usar o agente
   qa-tester para varreduras paralelas.

--------------------------------------------------------

FASE 1 — INVENTÁRIO E COBERTURA

Levante TODAS as funcionalidades expostas na UI (ações da toolbar,
menus, painéis, atalhos, diálogos — main_window.py e cut_mode_dialog.py)
e cruze com a suíte: o que NÃO tem teste de integração hoje?
A lista de buracos de cobertura é o mapa das fases seguintes.
Não assuma que algo funciona porque existe.

--------------------------------------------------------

FASE 2 — FLUXOS COMPLETOS (ida e volta)

Automatize de ponta a ponta, com verificação de RESULTADO (não só "não
crashou"):

Novo projeto → importar PDF → importar PNG → importar JPG/WEBP →
quantidade → Gerar Produção → duplicar (Ctrl+D, Ctrl+C/V, grade,
repetir) → girar (peça e documento) → mover com snap/guias → Gerar Faca
(auto/retângulo/contorno/vetor magenta do cliente) → exportar
(IMPRESSÃO.pdf, Faca PDF, DXF único, DXF por chapa) → salvar .printnest
→ fechar → reabrir → TUDO igual (posições, quantidades, overrides,
facas manuais, peças do Modo Corte se houver).

Modo Corte: arquivo SVG/PDF → Texto… → Organizar → arrastar peça +
tecla R → Exportar DXF → o DXF bate com o preview (posições/giros).

Abas: criar, alternar rápido, fechar com trabalho, clipboard por aba.

Exportação é o coração da venda: valide CONTEÚDO dos arquivos gerados
(abrir o PDF/DXF exportado e conferir geometria), não só a existência.

--------------------------------------------------------

FASE 3 — COMPORTAMENTOS INESPERADOS

Arquivo vazio. Arquivo corrompido (bytes aleatórios com extensão .pdf).
Arquivo que sumiu do disco depois de importado. PDF de 500 páginas.
Imagem enorme (ex. 12000×12000). PNG 100% transparente. JPEG CMYK.
PDF sem mídia/página. Nome com acento, emoji, 200 caracteres, espaço no
fim. Caminho de rede inexistente. 1000 arquivos na biblioteca. 10000
peças na chapa (mede, não trava?). Duplicar em cadeia até a chapa
estourar. Quantidade 999. Zoom extremo (mínimo e máximo). Undo/Redo ao
limite e intercalado com redesenho. Cancelar/fechar DURANTE a geração
(regressão do QA-08). Girar 4× = idêntico ao original. Salvar em pasta
sem permissão. Abrir .printnest corrompido/truncado/versão futura.
Dois PrintNest ao mesmo tempo (instância única).
Cada caso: ou vira teste, ou vira "suspeita por código" com trecho.

--------------------------------------------------------

FASE 4 — UX (o que dá para provar sem olho)

Tooltip: toda ação da toolbar tem? (varra _act/tool_button)
Atalhos: algum conflito (dois QShortcut na mesma tecla/contexto)?
Foco/tab order nos diálogos. Botão habilitado que não deveria (e
vice-versa) em cada estado: sem arquivo, sem produção, sem seleção.
Mensagens de erro: alguma exceção vaza traceback pro usuário em vez de
aviso? Textos: mistura de idioma, termo técnico sem tradução de
gráfica, label cortado (largura fixa + texto longo no código).
O que for julgamento visual → ROTEIRO MANUAL.

--------------------------------------------------------

FASE 5 — PERFORMANCE (medir, não achar)

Script de medição (tests/qa/ ou scratchpad; pode usar time.perf_counter
e tracemalloc/psutil se disponível):
- importar 1, 50, 200 arquivos → tempo cresce linear?
- Gerar Produção com 100/1000/5000 peças → tempo e pico de memória;
- redesenho (_draw_preview) com 1000 peças → tempo por chamada;
- arrastar com snap ligado e 500 peças na cena (o _snapped varre
  scene().items() — mede se é O(n) por movimento);
- exportar PDF/DXF grandes → tempo;
- repetir gerar+limpar 20× → memória volta? (vazamento de pixmap/cena);
- abrir/fechar Modo Corte 20× → idem.
Compare com o histórico: QAX-04 (seleção O(n²)) e QA-07 (footprint por
peça) já foram pegos antes — procure irmãos deles.
Nesting: cronometrar PODE, "otimizar" NÃO (motor congelado).

--------------------------------------------------------

FASE 6 — DESKTOP (roteiro manual para o Philipe)

Gere a checklist numerada: redimensionar janela ao mínimo; maximizar/
restaurar/minimizar com produção grande; FullHD e 4K; escala Windows
100/125/150/200% (texto cortado? ícone borrado?); dois monitores
(janela no 2º, DPI diferente); tema claro/escuro (troca ao vivo redesenha
os ícones?). No código, você audita o que dá: tamanho fixo em px,
fonte hardcoded, pixmap sem devicePixelRatio.

--------------------------------------------------------

FASE 7 — CONSISTÊNCIA

Varra por código: cor fora do theme.py (hex hardcoded — QA-06 já pegou
um)? Espaçamento mágico fora de theme.SPACE_*? Botão sem ícone onde os
irmãos têm? Ícone Lucide referenciado que NÃO existe em assets/icons
(sai vazio em silêncio)? Combos ilustrados: todos com tooltip por item?
Atalhos documentados = atalhos reais? Padrão de título/caption nos
diálogos?

--------------------------------------------------------

FASE 8 — DIA DE PRODUÇÃO (simulado por script)

Gere programaticamente um lote realista: 200 PDFs variados (tamanhos
diferentes, com e sem faca magenta) + 30 PNG + 20 JPG. Importe tudo,
quantidade variada, gere, faça faca, exporte o pacote completo, salve,
reabra, exporte de novo. Cronometre cada etapa e aponte O gargalo.
Repita o ciclo 3× na mesma sessão — degrada?

--------------------------------------------------------

FASE 9 — BUG HUNTING LIVRE

Crashes. Exceção engolida por try/except largo demais (procure
except Exception sem log). Estado inconsistente após undo/redo
(o _piece_rotations e o _faca_manual entram no snapshot?). Sinal Qt
conectado duas vezes. Referência Python solta que o GC coleta (a
história da chapa que sumia). Item de cena órfão. Diálogo modal que
pendura em offscreen. Race na thread de geração/nesting. Widget morto
recebendo sinal do tema. Duplicação/colar com id inexistente.

--------------------------------------------------------

FASE 10 — RELATÓRIO (docs/qa/RELATORIO-QA-<data>.md)

Para cada problema:
Título · Descrição · Passos para reproduzir · Resultado esperado ·
Resultado obtido · FONTE DA EVIDÊNCIA (teste/medição/código, com o
caminho do teste de reprodução) · Impacto · Probabilidade · Prioridade
· Criticidade · Sugestão de correção (sem aplicar!).

Classifique: 🔴 Crítico · 🟠 Alto · 🟡 Médio · 🟢 Baixo

No final:
1. Notas 0–10 com uma frase de justificativa cada: Estabilidade · UX ·
   UI · Performance · Consistência · Escalabilidade · Confiabilidade ·
   Prontidão para lançamento.
2. A checklist do ROTEIRO MANUAL (Fase 6 + itens visuais da Fase 4)
   para o Philipe rodar na máquina real.
3. O veredito honesto. Se for o caso, escreva:
   "NÃO APROVADO PARA PRODUÇÃO." — e a lista mínima do que destrava.
```
