# PrintNest Pro — bateria de testes 1.1.1

Fonte: `docs/qa/DOSSIE-PARA-BATERIA-DE-TESTES.md`.
Estado-alvo: 04/08/2026, versão 1.1.1, branch `release/1.0.1`.

Este plano não tenta provar que a tela "parece certa". Ele prova que o arquivo
que sai do PrintNest bate com o que o operador viu antes de mandar imprimir e
cortar. O veredito de cada frente precisa vir de medidas em PDF/DXF/imagem,
estado serializado ou logs, nunca só de inspeção visual.

---

## 1. Gates de aprovação

| Gate | Critério mínimo | Bloqueia venda? |
|---|---|---|
| G1 Arte × faca | Todas as combinações espelho × rotação exportam arte e faca sobrepostas, inclusive PDF com caixa invertida | Sim |
| G2 Crash Modo Corte | 200 ciclos de abrir/organizar/fechar Modo Corte sob GC forçado sem `0xc0000374`, sem crash log novo | Sim |
| G3 Estado por peça | Excluir, desfazer, refazer e rearrastar não ressuscitam giro/faca/espelho indevido; múltiplas cópias não somem juntas | Sim |
| G4 Primeira abertura | Instalador limpo abre sem auto-run, ativa, fecha e reabre sem pedir chave de novo | Sim |
| G5 CorelDRAW | Plugin envia seleção para o Modo Corte e recebe SVG/DXF de volta, ou falha com mensagem e timeout | Sim para público Corel |
| G6 Exportações | PDF, DXF, faca PDF e imagem preservam dimensões, coordenadas, unidades, marcas e orientação | Sim |
| G7 UI em telas pequenas | Telas 1366×768, 1280×720 e 1092×614 não ocultam comandos essenciais após `theme.apply()` | Não, mas bloqueia release se quebrar ativação/exportação |

---

## 2. Procedimento base

Executar primeiro a linha de base automatizada. O resultado válido é a soma dos
XML do JUnit, porque a suíte pode mentir no código de saída durante o teardown
do Qt.

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
.venv\Scripts\python.exe -m pytest tests --ignore=tests\presentation -q --junit-xml=reports\core.xml
foreach ($f in Get-ChildItem tests\presentation\test_*.py) {
  $xml = "reports\" + $f.BaseName + ".xml"
  .venv\Scripts\python.exe -m pytest $f.FullName -q --junit-xml=$xml
}
.venv\Scripts\python.exe reports\somar.py
```

Para UI com geometria, aplicar o tema antes de medir:

```python
from app.presentation import theme
theme.apply(app)
```

Artefatos de evidência ficam em `docs/qa/evidencias/1.1.1-2026-08-04/`:
PDFs exportados, DXFs, PNGs renderizados, XMLs do JUnit, logs de instalação,
prints de tela quando houver validação manual e `crash.log` quando existir.

---

## 3. Dados de teste obrigatórios

| ID | Arquivo sintético | Por que existe | Medição esperada |
|---|---|---|---|
| D1 | PDF assimétrico A4 com seta, texto e marca no canto superior esquerdo | Pega rotação invertida e espelho indevido | bbox da tinta e da faca coincidem após exportar |
| D2 | Mesmo PDF com MediaBox/TrimBox invertidas | Regressão de 03/08 | não espelha a arte e respeita recorte |
| D3 | PDF multipágina: páginas com tamanhos e boxes diferentes | Seleção de páginas e caixa Mídia/Apara | página importada tem dimensão escolhida |
| D4 | PDF com vetor magenta 100% do cliente | Faca do cliente | layer/contorno magenta vira faca sem deslocamento |
| D5 | PNG transparente com 5 adesivos, um deles de 4 mm, e ruído de 1 px | Recorte automático e sensibilidade | 5 facas reais, ruído ignorado |
| D6 | JPG com fundo branco e desenho assimétrico | Recorte de imagem comum | bbox desconta fundo e não corta tinta |
| D7 | SVG/DXF com letras e furos internos | Modo Corte true-shape | furos preservados e orientação correta no DXF |
| D8 | PDF corrompido, imagem 0×0, PDF sem páginas | Robustez | erro amigável, janela continua utilizável |
| D9 | Caminho com acento, espaço e UNC simulado | Windows real | import/export sem quebrar path |
| D10 | Projeto `.printnest` com versão futura e arquivo ausente | Compatibilidade | recusa versão futura; abre com aviso se asset sumiu |

---

## 4. Frentes de teste

### F1 — Arte e faca concordam no arquivo exportado

Risco coberto: 4.1.
Jornada: B9.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F1.1 | Matriz `mirror in ["", "h", "v", "hv"]` × `rotate in [0, 90, 180, 270]` no D1 | PDF de impressão, PDF da faca e DXF medidos | diferença máxima arte×faca ≤ 0,1 mm |
| F1.2 | Repetir F1.1 com D2 | PDFs medidos | sem espelho silencioso; recorte aplicado |
| F1.3 | Comparar cinco consumidores da regra canônica: faca, print PDF, preview, estado por peça e DXF | dump de coordenadas normalizadas | todos usam espelhar primeiro, girar depois |
| F1.4 | Chapa com 2 peças, uma girada 90° e outra 270° | overlay renderizado | nenhuma peça sai 180° invertida |
| F1.5 | Marcas de registro ligadas em PDF e DXF | coordenadas das marcas | marcas coincidem entre arquivos ≤ 0,1 mm |

Automatização permanente sugerida:
`tests/qa/test_qa_f4_art_faca_paridade.py`.

### F2 — Estado por peça, por arquivo e undo/redo

Risco coberto: 4.4.
Jornada: B6-B7.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F2.1 | Arrastar arquivo, girar, espelhar arte, espelhar faca, excluir peça e rearrastar o mesmo arquivo | snapshot de `_state_snapshot()` e exportação | nova peça começa sem giro/espelho/faca por peça |
| F2.2 | Criar 5 cópias do mesmo arquivo, selecionar uma, Delete | contagem na cena e no export | só a selecionada some |
| F2.3 | F2.2 + clique vazio + Ctrl+Z + Ctrl+Y | snapshots após cada passo | peças não reaparecem de forma fantasma |
| F2.4 | Faca manual por arquivo, depois excluir só uma peça | projeto salvo e reaberto | override por arquivo persiste onde esperado; estado por peça removido |
| F2.5 | Trocar de aba depois de overrides e desfazer | snapshots por aba | estado não vaza entre projetos |

Automatização permanente sugerida:
ampliar `tests/presentation/test_desfazer_excluir_espelhar.py` e
`tests/qa/test_qa_f2b_estado.py`.

### F3 — Modo Corte: concorrência, true-shape e giro

Riscos cobertos: 4.2, 4.5, 4.7.
Jornada: C4-C6.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F3.1 | 200 ciclos: abrir diálogo, importar D7, organizar com 15°/45°/90°, fechar; `gc.collect()` durante worker | log, ausência de crash, XML | zero crash, zero objeto órfão, UI responsiva |
| F3.2 | Rodar duas otimizações idênticas com seed fixa/dados iguais | DXF e dump de layouts | rotações permitidas aparecem de modo determinístico ou justificadamente equivalente |
| F3.3 | Mover/girar peça no preview e exportar DXF | entidades DXF medidas | DXF lê `self._layouts` final |
| F3.4 | Fechar janela durante organização | estado pós-fechamento | thread termina sem escrever em widget morto |
| F3.5 | Organizar 100 letras com furos | interseção Shapely e DXF | sem sobreposição real, furos preservados |

Automatização permanente sugerida:
`tests/qa/test_qa_f4_cut_mode_concurrency.py`.

### F4 — Importação e biblioteca

Riscos cobertos: 3.1, 4.9.
Jornada: B2-B3.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F4.1 | Importar PDF, PNG, JPG, WEBP por botão e drag-and-drop | contagem na biblioteca | formatos aceitos entram com dimensão correta |
| F4.2 | Arrastar `.cdr` e `.svg` na produção de impressão | mensagem capturada | usuário recebe orientação, não silêncio |
| F4.3 | Substituir arquivo com produção montada | snapshot e export | arranjo atualiza sem estado antigo indevido |
| F4.4 | Quantidade 200 digitada rapidamente | tempo e chamadas de relayout | não recalcula a cada dígito se houver debounce |
| F4.5 | PDF multipágina D3, escolher páginas alternadas e caixa Mídia/Apara | dimensões por item | seleção e caixa obedecidas |

### F5 — Faca de corte

Riscos cobertos: 3.3, 4.1, 4.4.
Jornada: B7.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F5.1 | Gerar Automático, Retângulo, Contorno justo, suave, simplificado e Faca do cliente | área, bbox, nós | contorno esperado por modo |
| F5.2 | Sangria +3 mm e -2 mm | área/bbox antes/depois | crescimento/recuo dentro de tolerância |
| F5.3 | Cantos vivos, arredondados e chanfrados com raio configurado | geometria dos vértices | raio e chanfro corretos |
| F5.4 | Densidade fino/médio/leve | contagem de nós | contagem decresce sem deformar retas |
| F5.5 | Solda de facas que se invadem | área da união | vira um contorno, sem auto-interseção |
| F5.6 | Pontos/F10: mover, adicionar, remover nó | coordenadas exportadas | edição manual aparece no PDF/DXF |

### F6 — Nesting de impressão

Riscos cobertos: desperdício de chapa, estado acumulado.
Jornada: B4-B6.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F6.1 | 5 PDFs × quantidades variadas em chapa 1250×1992 mm | bboxes | peças dentro da chapa, sem sobreposição |
| F6.2 | Espaçamento horizontal/vertical e margem de segurança | distância mínima | respeita campos em 0,1 mm |
| F6.3 | Divisão em múltiplas chapas | contagem por página/export | nenhuma peça perdida ou duplicada |
| F6.4 | Repetir em grade, duplicar, resetar arranjo | snapshots | comandos preservam invariantes |
| F6.5 | Aproveitamento exibido | cálculo independente | percentual bate com área ocupada/chapa |

### F7 — Exportações

Riscos cobertos: 3.6, 4.1.
Jornada: B9-B10.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F7.1 | PDF de impressão com vetor preservado | inspeção pikepdf/fitz | página no tamanho correto, arte vetorial quando entrada for vetor |
| F7.2 | DXF único e por chapa | ezdxf | unidades mm, layer CUT, Y correto, curvas como splines |
| F7.3 | Faca em PDF, IECHO e Mimaki | contagem/posição de marcas | formato e afastamento corretos |
| F7.4 | Imagem PNG/JPEG em DPI escolhido | PIL | pixels = mm × DPI / 25,4 |
| F7.5 | Caminho inválido, sem permissão ou arquivo aberto | mensagem e retorno | erro amigável, sem exceção engolida |
| F7.6 | Exportar sem faca gerada | mensagem | recusa clara |

### F8 — Projeto, sessão e recuperação

Riscos cobertos: 3.7, Jornada E.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F8.1 | Salvar e reabrir projeto com quantidades, overrides, faca manual, tema e abas | comparação estado a estado | roundtrip idêntico |
| F8.2 | Gravação atômica com falha simulada | arquivos no disco | projeto anterior permanece íntegro |
| F8.3 | Reabrir último projeto ao iniciar | config temporária | carrega o esperado, sem pedir ação |
| F8.4 | Dirty flag: fechar intocado, alterado e Cancelar | diálogos capturados | só pergunta quando deve; Cancelar aborta |
| F8.5 | Crash log existente em `%APPDATA%` | inicialização e logs | app não falha por log antigo; suporte consegue localizar |

### F9 — Instalação, primeira abertura e atualização

Riscos cobertos: 4.3, 3.9.
Jornadas: A, D.

Casos manuais em VM limpa:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F9.1 | Instalar 1.1.1 com Windows Defender ativo | vídeo/log Inno | instalador não autoabre o app |
| F9.2 | Abrir imediatamente após instalar | log `%TEMP%` e tela | sem "Failed to load Python DLL" |
| F9.3 | Ativar licença válida, fechar, reabrir | config/licença | não pede ativação de novo |
| F9.4 | Manifesto aponta versão nova | print e URL aberta | aviso aparece e link funciona |
| F9.5 | Sem internet | mensagem | não diz que está em dia se não verificou |
| F9.6 | Instalar por cima de versão anterior | log Inno e config | licença e configurações preservadas |

### F10 — CorelDRAW real

Riscos cobertos: 4.6.
Jornadas: C1, C6.

Casos em máquina com CorelDRAW:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F10.1 | Instalar macro e botão | print/video | botão aparece e chama PrintNest |
| F10.2 | Seleção simples no Corel → Modo Corte | arquivo intermediário e tela | dimensão preservada |
| F10.3 | Seleção com texto convertido/curvas/furos | DXF/SVG | furos e curvas preservados |
| F10.4 | Corel ocupado com diálogo aberto | tempo e mensagem | PrintNest não congela indefinidamente |
| F10.5 | Enviar p/ Corel após organizar | Corel aberto | objeto volta no tamanho e posição esperados |

### F11 — UI, idioma e acabamento

Riscos cobertos: 4.8, 4.9.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F11.1 | Resoluções 1920×1080, 1536×864, 1366×768, 1280×720, 1092×614 | screenshots e medições Qt | botões essenciais visíveis |
| F11.2 | Escalas 100%, 125%, 150% | screenshots | ativação e exportação cabem |
| F11.3 | Varredura de textos sem acento e Yes/No | grep/teste | português completo onde visível |
| F11.4 | Exportação de imagem grande | tempo e responsividade | sem janela "Não respondendo" se worker existir; caso contrário registrar risco |
| F11.5 | Modo Corte preview | interação manual | zoom ausente registrado como pendência, sem prometer cobertura |

### F12 — Robustez e desempenho

Riscos cobertos: 4.2, 4.5, 4.9.

Casos:

| ID | Caso | Evidência | Critério |
|---|---|---|---|
| F12.1 | Importar 50 arquivos | tempo | sem crash, tempo registrado |
| F12.2 | Gerar 500 peças | tempo, memória, bboxes | sem sobreposição e sem travar UI permanentemente |
| F12.3 | Exportar job completo com várias chapas | tempo e arquivos | todos os arquivos abrem e medem certo |
| F12.4 | Gerar duas vezes rápido, fechar durante worker, alternar abas durante worker | logs/snapshots | sem corrupção de estado |
| F12.5 | Comparar com `scripts/benchmark.py` quando aplicável | relatório | regressão >30% vira bug |

---

## 5. Ordem de execução recomendada

1. Linha de base automatizada completa.
2. G1: F1 + F7, porque erro aqui estraga material.
3. G2: F3 e F12 concorrência, porque crash perde trabalho.
4. G3: F2, porque há defeito diagnosticado e não corrigido.
5. G4/G5: F9 e F10 em máquina limpa com CorelDRAW.
6. F4, F5, F6 e F8 para cobertura funcional ampla.
7. F11 para acabamento e telas pequenas.

---

## 6. Modelo de bug

```markdown
### BUG-<n> — <título curto>

Severidade: 🔴 crítico | 🟠 alto | 🟡 médio | 🟢 baixo
Frente: F<id>
Ambiente: versão, branch, Windows, escala, resolução, CorelDRAW se houver

Passos:
1. ...

Esperado:
...

Obtido:
...

Evidência:
- Arquivo:
- Medida:
- Screenshot/log:

Causa raiz:
`app/...py:<linha>` — ...

Teste permanente que teria pego:
`tests/.../test_...py::test_...`
```

---

## 7. Entregável da execução

Criar `docs/qa/RELATORIO-QA-1.1.1-2026-08-04.md` com:

- resumo executivo com total de casos executados, aprovados, falhados e bloqueados;
- tabela ✅/❌/⚠️ por frente F1-F12;
- bugs ordenados por severidade;
- evidências anexadas por caminho;
- testes pytest permanentes propostos para cada bug;
- veredito final: "pronto para vender?", sim ou não, com ressalvas explícitas.

Veredito só pode ser "sim" se G1, G2, G3, G4 e G6 passarem. Para venda ao
público CorelDRAW, G5 também precisa passar em máquina real.
