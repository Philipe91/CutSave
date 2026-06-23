# PrintNest — Estado do Projeto

> **Data:** 23/06/2026
> **Versão atual:** V1.1 (protótipo em produção real na gráfica)
> **Stack:** Python 3.10 · PySide6 · PyMuPDF (fitz) · Shapely · ezdxf · pytest
> **Repositório:** github.com/Philipe91/CutSave (branch `main`)
> Documento de acompanhamento. Complementa [ARQUITETURA.md](ARQUITETURA.md) e [ROADMAP.md](ROADMAP.md).

---

## 1. O que é o PrintNest (resumo de uma frase)

Software desktop Windows, em português, que **prepara arquivos para produção gráfica**: importa o PDF do cliente → define a caixa de corte → gera a **faca** (linha de corte) com offset/recuo → faz o **nesting** (encaixe das peças na chapa) → **exporta o PDF de impressão e o DXF de corte**.

**Não controla máquina.** Entrega arquivos prontos; o operador segue usando o software da máquina. O objetivo é **substituir o nesting/corte do Print Factory** e eliminar a licença recorrente.

---

## 2. Como o projeto está organizado (arquitetura)

Clean Architecture em 4 camadas, com o **motor independente da interface** (tudo em milímetros internamente):

| Camada | Pasta | Papel |
|---|---|---|
| **Domínio** | `app/domain/` | Regras puras: geometria, faca, nesting. Sem dependência de UI/PDF. |
| **Aplicação** | `app/application/` | Casos de uso e portas (interfaces). Orquestra o domínio. |
| **Infraestrutura** | `app/infrastructure/` | Implementações concretas: PyMuPDF, ezdxf, renderização. |
| **Apresentação** | `app/presentation/` | Interface PySide6 (janela, canvas, painéis). |

**Estado de qualidade:** **283 testes automatizados passando** (43 arquivos de teste), **ruff** (lint) limpo. Testes-ouro de geometria e nesting rodam sem abrir a interface.

---

## 3. TUDO que já foi feito (linha do tempo)

Histórico real de commits, do mais antigo ao mais recente:

| Commit | Entrega |
|---|---|
| `719c6a7` | **MVP**: importação PDF, faca, nesting, exportação PDF/DXF + interface inicial |
| `2c47aa7` | Preview com arte + faca, multi-chapa, recuo de segurança, remover PDF |
| `315eec7` | Faca compartilhada (grade fora a fora) e 5 marcas de registro |
| `2cd10be` | Recorte da arte (clip de bordas) para emendas sem linha branca |
| `653312d` | UI por categorias, registro Mimaki (marcas em L + quadro) e rotação |
| `549d6db` / `a888935` | Faixas modernas separando categorias; seções recolhíveis (clicar abre/fecha) |
| `a82dc14` | **V1.1 P1**: quantidade por item (coluna Qtd) |
| `493f380` | V1.1: modos de visualização e medida do arquivo selecionado |
| `5a92427` | Remoção de binários de build do versionamento (.exe/.ico) |
| `a83d8ff` | **V1.1**: caixa Mídia/Apara, faca enquadrada e ferramentas estilo CorelDRAW |
| `8939e13` | Exportar impressão em imagem (PNG/JPEG) com DPI — *commit local, ainda não publicado* |

### 3.1. Núcleo de processamento (motor)
- **Importação de PDF** com dimensão real (pt→mm) e escolha da caixa: **Mídia** (mantém sangria/marcas) ou **Apara** (corta no traço de corte do PDF). Prioridade automática TrimBox > CropBox > MediaBox.
- **Geração de faca retangular** com **offset** (sangria, faca para fora) e **recuo de segurança** (faca para dentro).
- **Recorte da arte** (remove faixa branca da borda para emendas perfeitas).
- **Faca por peça** (quadrados individuais) **ou compartilhada** (grade fora a fora, economiza corte).
- **Quantidade por item** (modelo *flyweight*: 1 arte → N cópias, suporta milhares).
- **Nesting automático em grade** com divisão em **múltiplas chapas** quando não cabe tudo.
- **Rotação** global (0/90/180/270°).

### 3.2. Marcas de registro
- **Bolinhas (5)** ao redor do trabalho.
- **Mimaki** (marcas em L nos cantos + quadro), com distância/tamanho/espessura configuráveis.

### 3.3. Exportação
- **PDF de impressão** — vetores preservados (sem rasterizar), uma página por chapa.
- **DXF de corte** — em mm, layers CUT e REGMARK, no mesmo referencial do PDF.
- **DXF por chapa** — um arquivo por chapa (`CORTE_01.dxf`, `CORTE_02.dxf`…).
- **Seleção de chapas na exportação** — escolher quais chapas sair (ex.: `1,3-5`), tanto no PDF quanto no DXF.
- **Imagem PNG/JPEG com DPI escolhido** (novo) — rasteriza a impressão na resolução pedida; numera as chapas quando há mais de uma.

### 3.4. Interface (estilo CorelDRAW)
- **Área de trabalho** com zoom (roda), pan (botão do meio), mesa cinza e **réguas em mm**.
- **Painel por categorias** em faixas coloridas recolhíveis (Arquivo, Chapa, Faca, Registro, Exibição).
- **Configuração em tempo real**: mexeu no offset/recuo/recorte/chapa, o preview atualiza na hora; o **zoom é preservado** ao mudar parâmetro.
- **Modos de visualização**: impressão + corte, só impressão, só corte, ou tela dividida.
- **Medida do arquivo selecionado** numa caixa dedicada.
- **Edição no canvas estilo Corel** (entregue na última rodada):
  - **Mover, selecionar, selecionar tudo, excluir, resetar arranjo**.
  - **Agrupar / desagrupar** e **desfazer/refazer (Ctrl+Z / Ctrl+Y)**.
  - **Empurrar com as setas** (1 mm; Ctrl = 0,1 mm; Shift = 10 mm).
  - **Alinhar e distribuir** (menu Organizar): esquerda/direita/topo/base, centralizar, distribuir espaçamento igual.
  - **Duplicar (Ctrl+D)** e **Repetir em grade / step-and-repeat (Ctrl+Shift+D)**.
  - **Encaixe magnético (snap)** ao arrastar — gruda nas bordas/centro das outras peças e da chapa (Alt+Q liga/desliga).
- **Menu + barra de ferramentas** completos, com **dicas (tooltips)** ao passar o mouse.
- **Seletor de quantidade moderno** (botões − / +).
- **Configurações persistidas** entre sessões.

### 3.5. Build / empacotamento
- Executável Windows único via **PyInstaller** (Python embarcado, não exige instalação de Python). Pasta `PrintNest_Build/` (fora do versionamento).

---

## 4. Onde estamos (mapa contra o Roadmap oficial das 23 fases)

| Fase | Tema | Situação |
|---|---|---|
| 1 | Estruturação do projeto | ✅ Concluída |
| 2 | Modelo de domínio | ✅ Concluída |
| 3 | Importação PDF | ✅ Concluída (+ caixa Mídia/Apara) |
| 4 | Importação PNG | ❌ Pendente |
| 5 | Importação JPG | ❌ Pendente |
| 6 | Miniaturas / cache | 🟡 Parcial (preview com cache em memória; sem cache em disco por hash) |
| 7 | Faca PDF vetorial | 🟡 Parcial (núcleo existe; UI usa faca retangular) |
| 8 | Faca PNG (alpha) | ❌ Pendente |
| 9 | Faca JPG | ❌ Pendente |
| 10 | Motor de offset | 🟡 Parcial (offset/recuo retangular pronto; buffer Shapely para contornos quaisquer pendente) |
| 11 | Quantidades | ✅ Concluída |
| 12 | Biblioteca de materiais | ❌ Pendente (modelo Material existe; faltam perfis salvos) |
| 13 | Nesting V1 | 🟡 Grade pronta; MaxRects e rotação por peça pendentes |
| 14 | Visualizador | ✅ Concluída (+ ferramentas Corel) |
| 15 | Sistema de Jobs (background) | 🟡 Parcial (thread com progresso; sem fila/cancelamento) |
| 16 | Exportação PDF | ✅ Concluída (+ imagem PNG/JPEG) |
| 17 | Exportação DXF | ✅ Concluída (+ por chapa) |
| 18 | Testes reais de carga (100–5000) | ❌ Pendente |
| 19 | Nesting V2 (Skyline/otimização) | ❌ Pendente |
| 20 | Cache unificado | ❌ Pendente |
| 21 | Otimização de performance (ProcessPool) | ❌ Pendente |
| 22 | Beta interno | 🟡 Em andamento (já em uso real na gráfica) |
| 23 | Release 1.0 | ❌ Pendente (build V1.1 protótipo existe) |

**Resumo:** o **fluxo principal de produção (PDF → faca → nesting → PDF/DXF) está completo e em uso**. O que falta é majoritariamente **ampliar formatos (PNG/JPG), inteligência de nesting, materiais salvos e performance em escala**.

---

## 5. O que falta fazer (priorizado)

### Curto prazo — itens V1.1 pendentes (camada de apresentação, baixo risco)
1. **Padronizar em centímetros** — alternar a interface inteira (campos, réguas, medida) entre mm e cm. Motor continua em mm. *(Prioridade EXTRA já solicitada.)*
2. **Rotação por peça** — girar peças individualmente no canvas (hoje a rotação é global).
3. **Salvar/abrir projeto (.printnest)** — guardar PDFs, quantidades e parâmetros; reabrir depois; reabrir último projeto.
4. **Estatísticas** — nº de chapas, aproveitamento de material, total de peças.

### Médio prazo — completar o núcleo (Roadmap)
5. **Importação PNG e JPG** (Fases 4–5) e **faca por contorno/alpha** (Fases 7–9).
6. **Biblioteca de materiais** (Fase 12) — perfis reutilizáveis (Adesivo, Lona, PVC, ACM…).
7. **Nesting V2** (Fase 19) — melhor aproveitamento (MaxRects/Skyline).

### Longo prazo — maturidade e release
8. **Testes de carga** (Fase 18), **cache unificado** (Fase 20), **performance/ProcessPool** (Fase 21).
9. **Release 1.0** (Fase 23) — instalador final após beta.

---

## 6. Pendências de processo (decisões suas)

- **Publicar o último commit:** `8939e13` (exportar imagem PNG/JPEG) está **commitado localmente mas não foi enviado** ao GitHub — aguardando sua liberação para o `git push`.
- **Rebuild do .exe:** as últimas funcionalidades (caixa Mídia/Apara, ferramentas Corel, exportação de imagem) ainda **não estão no executável** — falta rodar o `build.bat` quando você aprovar.
- **Histórico do Git:** um `.exe` grande (~84 MB) foi commitado por engano numa rodada anterior; já foi removido do versionamento (`5a92427`), mas o blob ainda existe no histórico — posso limpar com `git filter-repo` quando quiser.
- **Arquivos de cliente:** PDFs/DXFs continuam **fora do versionamento** (`.gitignore`), por segurança.

---

## 7. Próximo passo sugerido

Recomendo, na ordem: **(a)** liberar o push do `8939e13`; **(b)** seguir com **padronização em cm** (presentation-only, baixo risco, alto valor no dia a dia da gráfica); **(c)** depois **salvar/abrir projeto**, que destrava o uso recorrente. É só dizer por onde seguimos.
