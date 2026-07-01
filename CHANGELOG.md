# Changelog

Todas as mudanças relevantes do PrintNest Pro. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/). O histórico detalhado por
sessão fica em [`docs/historico/`](docs/historico/).

## [Não lançado] — branch `v1.2-projeto`

### V2.0 — UX/UI orientada ao operador (estilo CorelDRAW)
Só camada de edição/apresentação — motor, nesting, DXF e PDF **intactos**.

#### Adicionado
- **Barra de propriedades contextual** (Projeto / Objeto / Grupo), abaixo da ribbon.
- **Ferramenta Contorno** (faca): Offset + Direção (externo/interno) + Cantos
  (redondo/ponta/chanfro), só-ícone com tooltip. Cantos no motor via `join_style`.
- **Faixa Faca** (Modo/Recorte/Giro/Suavizar), global, sincronizada com o Documento.
- **Alças de mouse** para redimensionar a peça (com prévia; respeitam o cadeado).
- **Cadeado** de proporção no contexto Objeto.
- Checkbox **"Manter centralizado na chapa"** (sincronizado com o menu Organizar).

#### Alterado
- **"Gerar Faca"** virou o botão azul principal; "Gerar Produção" foi ao menu Ferramentas.
- Documentação reorganizada para `docs/` (por tema) com índice.

#### Removido (enxugar duplicações)
- Card "Medidas da peça" e campos L/A da barra (a medida já aparece no Objeto).
- Controle de "Densidade" (substituído pela ferramenta Contorno).

#### Corrigido
- Excluir a **última** peça (e remover da biblioteca) agora tira a arte da tela.
- **Girar** mantém a seleção (re-seleciona por `artwork_id` após o re-encaixe).

### Sessões anteriores (resumo)
- **29/06:** rotação por peça, marcas de registro na faca (bolinhas pretas),
  duplicar página, centralizar na página, quantidade nativa, correção da sangria.
- **25/06:** redimensionar arquivos, Ctrl+Z ilimitado, nesting MaxRects, Centro de
  Exportação, integração CorelDRAW (macro + instância única).
- **22–24/06:** faca compartilhada e marcas, base de nesting e exportação.

> Detalhes completos em `docs/historico/ESTADO-*.md`.
