# Plano de Comercialização — PrintNest

> Tudo o que falta para **vender o PrintNest na internet de forma legal e profissional**: licenciamento/ativação (estilo eCut), segurança e confiabilidade, desempenho, qualidade, jurídico/fiscal e distribuição.
>
> Status: o **produto técnico** (preparação de produção: faca, nesting, export PDF/DXF) já existe e está testado. Este plano cobre o que envolve **transformar o software em um produto comercial**.

---

## 0. Resumo executivo — o caminho mais curto para vender

Ordem recomendada (cada item destrava o próximo):

1. **Definir a empresa/figura jurídica** (MEI ou ME) para emitir nota fiscal de software/licença.
2. **Licenciamento e ativação** (item 1 abaixo) — sem isso não há venda controlada.
3. **Assinatura digital do instalador** (code signing) — sem isso o Windows/antivírus bloqueia.
4. **EULA + Política de Privacidade (LGPD)** — obrigações legais mínimas.
5. **Plataforma de venda + pagamento** (Hotmart/Mercado Pago/Stripe) integrada à emissão de licença.
6. **Atualização automática + suporte** — sustenta o cliente no longo prazo.

> **Decisão central:** comprar um serviço pronto de licenciamento (Cryptolens, Keygen.sh, LicenseSpring) **ou** construir um servidor próprio. Recomendação: **começar com serviço pronto** (semanas, não meses; menos risco de segurança) e internalizar depois se o volume justificar.

---

## 1. Licenciamento e ativação (modelo "estilo eCut")

### 1.1 O que o cliente vive (fluxo desejado)
1. Compra no site → recebe por e-mail um **código de licença** (chave única, unitária).
2. Instala o PrintNest, abre, cola o código e clica **Ativar**.
3. O programa fica **liberado naquele PC**.
4. Para trocar de PC, clica **Desativar** (libera o "assento") e **Ativa** no novo PC com o mesmo código.
5. Se esquecer de desativar (PC quebrou), pede liberação ao suporte (reset do assento).

Isso é exatamente o modelo **node-locked com ativação online e self-transfer** (1 licença = 1 ativação simultânea). É o padrão de mercado (eCut, CorelDRAW, etc.).

### 1.2 Como funciona por dentro (anti-pirataria realista)
- **Chave de licença**: string única gerada no servidor por compra (ex.: `PNEST-XXXX-XXXX-XXXX`). Guardada no banco com status (ativa, assentos usados, cliente).
- **Impressão digital da máquina (machine fingerprint)**: o app calcula um ID estável do PC (combinação de: volume serial do disco, MAC, modelo de CPU, nome da máquina — com tolerância para pequenas mudanças). É o que "prende" a licença ao computador.
- **Ativação online**: app envia `chave + fingerprint` ao servidor → servidor verifica se a chave é válida e tem assento livre → registra o par e devolve um **token de licença assinado** (assinatura criptográfica RSA/ECDSA).
- **Validação offline**: o app guarda o token assinado localmente e **verifica a assinatura com a chave pública embutida** no executável. Assim funciona offline por um período (ex.: revalida a cada 15–30 dias quando houver internet). A chave **privada** nunca sai do servidor.
- **Desativação**: app avisa o servidor → libera o assento → apaga o token local.
- **Limite de ativações**: 1 (ou N) simultâneas por chave; trocar de PC = desativar + ativar.

> **Verdade importante sobre pirataria:** nenhum esquema em software desktop é 100% inquebrável (o código roda na máquina do cliente). O objetivo realista é **tornar a pirataria mais trabalhosa do que comprar** e proteger contra cópia casual (passar o instalador + chave para o amigo). A combinação **ativação online + token assinado + fingerprint + code signing + ofuscação leve** atinge isso. Investir em anti-tamper pesado tem retorno decrescente.

### 1.3 Componentes a construir/contratar
| Componente | Onde | Esforço |
|---|---|---|
| **Servidor de licença** (API: ativar, desativar, validar, reset) | nuvem (ou serviço pronto) | médio (ou contratado) |
| **Banco de licenças** (chave, cliente, assentos, status, histórico) | Postgres/SQLite gerenciado | baixo |
| **Geração de chaves** ligada à venda | webhook do gateway de pagamento | baixo |
| **Cliente no app** (tela Ativar/Desativar, fingerprint, validação do token) | `app/licensing/` (novo módulo) | médio |
| **Assinatura do token** (par de chaves RSA/ECDSA; pública embutida no app) | servidor | baixo |
| **Modo de avaliação** (trial 7–15 dias) e **período de carência offline** | app + servidor | baixo |

### 1.4 Opções de implementação (recomendação)
| Opção | Prós | Contras |
|---|---|---|
| **Serviço pronto** — Cryptolens, Keygen.sh, LicenseSpring | Rápido, seguro, pronto p/ Python; cuida de servidor/segurança | Custo mensal; dependência externa |
| **Servidor próprio** (FastAPI + Postgres + JWT/assinatura) | Controle total, sem mensalidade por licença | Você mantém segurança, uptime, backups |
| **Híbrido** | Começa com serviço pronto, migra depois | — |

**Recomendado:** começar com **serviço pronto** (ex.: Cryptolens tem SDK Python e suporta node-locked + ativação/desativação) para validar o negócio com risco baixo; reavaliar servidor próprio quando o volume justificar.

### 1.5 Onde encaixa no código
- Novo módulo isolado: `app/licensing/` (cliente da API, fingerprint, cache do token, verificação de assinatura).
- Tela de ativação na inicialização (`app/presentation`): se não houver licença válida, abre o diálogo Ativar/Trial antes da janela principal.
- **Não acoplar** licença ao núcleo (domínio): é uma camada de borda, como as outras. Mantém o resto testável e intacto.

---

## 2. Segurança e confiabilidade

### 2.1 Distribuição segura
- **Assinatura digital de código (code signing)**: certificado **OV** ou, ideal, **EV** (Windows confia de cara, menos alerta SmartScreen). Custo anual; emitido para a pessoa jurídica. **Item bloqueador** — sem isso o Windows Defender/SmartScreen assusta o cliente.
- **Instalador profissional**: Inno Setup ou NSIS sobre o build PyInstaller (atalhos, desinstalador, versão).
- **Build reproduzível** e verificado em **PC limpo** (sem Python) antes de cada release.

### 2.2 Atualização automática
- Mecanismo de auto-update (ex.: checagem de versão + download assinado, ou ferramenta como `WinSparkle`/`PyUpdater`).
- Canal de versão (estável/beta) e changelog visível ao cliente.

### 2.3 Confiabilidade e suporte a incidentes
- **Relatório de erros (crash reporting)**: capturar exceções não tratadas → log + opção de enviar (com consentimento) ao suporte (ex.: Sentry self-host ou e-mail). Hoje já há logging estruturado em `app/shared/logging`.
- **Logs com correlation id por job** (já previsto na arquitetura) para diagnosticar lote a lote.
- **Backup/recuperação de projeto**: salvar `.printnest` é o ponto de recuperação; considerar autosave/versão temporária.
- **Resiliência de lote**: um arquivo com erro não derruba o trabalho inteiro (já é princípio do projeto).

### 2.4 Privacidade (LGPD) — ver também item 5
- Coletar o **mínimo** (e-mail, chave, fingerprint). Fingerprint é dado técnico, mas associado ao cliente vira dado pessoal → declarar na Política de Privacidade.
- Dados de licença trafegam por **HTTPS**; em repouso, banco protegido.

---

## 3. Desempenho

### 3.1 O que medir (cenários reais de gráfica)
| Cenário | Métrica alvo (referência inicial) |
|---|---|
| Importar 1 PDF/imagem | < 1 s por arquivo |
| Importar lote de 50–100 arquivos | progresso fluido, UI nunca trava |
| Gerar faca de imagem (contorno) | < 0,5 s por imagem típica |
| Nesting de milhares de cópias idênticas | segundos (grade), com barra de progresso |
| Preview no canvas (zoom/pan) | 60 fps na navegação |
| Exportar PDF/DXF | sem estourar memória mesmo em chapas grandes |

### 3.2 Como testar
- **Benchmark automatizado**: ver `scripts/benchmark.py` (mede importação + faca + nesting em dados sintéticos e imprime tempos). Rodar antes de cada release e comparar com o histórico.
- **Profiling** quando algo passar do alvo: `cProfile`/`py-spy` para achar o gargalo real (não otimizar no escuro).
- **Teste de carga manual**: um job real grande de produção (centenas de peças) cronometrado.

### 3.3 Riscos de desempenho conhecidos (já mapeados na arquitetura)
- Memória com milhares de cópias → flyweight (1 arte ↔ N posições), proxies, cache.
- GIL travando a UI → trabalho pesado em thread/worker (já existe `ProductionWorker`).
- Vetorização/contorno pesado → simplificação e limite de vértices.

---

## 4. Qualidade e testes

### 4.1 Situação atual
- **380+ testes** (pytest) cobrindo domínio, aplicação e apresentação (UI offscreen). Boa base.

### 4.2 O que adicionar para "nível de produto"
- **Cobertura medida**: `pytest --cov` com meta (ex.: ≥ 80% no domínio/aplicação).
- **CI (integração contínua)**: rodar testes + lint a cada push (GitHub Actions). Bloquear merge se quebrar.
- **Lint/format**: `ruff` (lint) e `black` (format) padronizados.
- **Matriz de teste manual** (checklist de release): importar cada tipo, gerar faca (retângulo/contorno/imagem), nesting, exportar PDF e DXF, abrir o DXF num software de corte, salvar/abrir projeto, ativar/desativar licença, instalar em PC limpo.
- **Agente de QA**: ver `.claude/agents/qa-tester.md` — agente especializado para revisar mudanças, sugerir/escrever testes e rodar a suíte de forma disciplinada.

### 4.3 Definição de "pronto para release"
Todos os testes verdes · benchmark dentro das metas · instalador assinado testado em PC limpo · checklist manual ok · changelog escrito.

---

## 5. Jurídico e fiscal (Brasil)

> Não é aconselhamento jurídico — validar com contador/advogado. É a lista do que normalmente é necessário.

| Item | Por quê |
|---|---|
| **Figura jurídica** (MEI/ME/EPP) | Emitir nota fiscal de venda de licença de software |
| **Nota fiscal** (NFS-e de software/licenciamento) | Obrigação fiscal; muda conforme município/regime |
| **Tributação** | Software como serviço/licença tem ISS/regras próprias — confirmar com contador |
| **EULA (Contrato de Licença de Usuário Final)** | Define que se vende **licença de uso**, não o software; limita responsabilidade, proíbe revenda/engenharia reversa |
| **Política de Privacidade (LGPD)** | Coleta de e-mail/fingerprint exige base legal, finalidade e direitos do titular |
| **Termos de Venda / reembolso** | Direito de arrependimento (CDC, 7 dias em compra online); política de reembolso clara |
| **Marca (INPI)** | Registrar o nome/marca "PrintNest" para proteger e poder vender com exclusividade |
| **Licenças de terceiros** | Inventário das libs (PySide6 = LGPL com linking dinâmico; PyMuPDF = **AGPL** — atenção, pode exigir licença comercial da Artifex para uso fechado!), Shapely/OpenCV/etc. |

> ⚠️ **Atenção crítica — PyMuPDF (AGPL):** o PrintNest usa PyMuPDF (fitz), que é **AGPL/licença comercial**. Para vender software proprietário, é preciso **comprar a licença comercial da Artifex** ou **substituir** a dependência (ex.: `pypdfium2` para render, outra lib para extração). **Resolver isto antes de vender.** É o maior risco jurídico atual.

---

## 6. Distribuição e vendas

### 6.1 Entrega
- **Site/landing page** com demonstração, preço, botão de compra e download do instalador (trial).
- **Gateway de pagamento + emissão de licença**: ex.: **Hotmart/Eduzz** (cuidam de pagamento, nota, antifraude e já entregam por e-mail) ou **Mercado Pago/Stripe** + webhook que gera a chave no servidor de licença.
- **E-mail automático** com a chave e instruções de ativação.

### 6.2 Pós-venda
- **Suporte** (e-mail/WhatsApp/portal) — inclui reset de assento quando o cliente troca de PC sem desativar.
- **Atualizações** entregues por auto-update.
- **Documentação do usuário** (manual/vídeos curtos: instalar, ativar, importar, gerar faca, exportar).

### 6.3 Modelo de preço (a decidir)
- **Licença perpétua** (paga uma vez) + atualizações por período, **ou**
- **Assinatura** (mensal/anual) — receita recorrente, combina bem com validação online periódica.

---

## 7. Custos recorrentes estimados (ordem de grandeza)
| Item | Frequência |
|---|---|
| Certificado de code signing (OV/EV) | anual |
| Serviço de licenciamento (se contratado) | mensal/por licença |
| Servidor/nuvem (se próprio) | mensal |
| Domínio + site/landing | anual/mensal |
| Taxa do gateway de pagamento | % por venda |
| Licença comercial PyMuPDF (se mantida) | conforme Artifex |
| Contador | mensal |

---

## 8. Checklist priorizado (do bloqueador ao desejável)

**Bloqueadores (sem isto não dá para vender legal/seguro):**
- [ ] Resolver licença do **PyMuPDF** (comprar comercial ou trocar a dependência)
- [ ] **Licenciamento/ativação** (servidor + cliente + chave única + ativar/desativar)
- [ ] **Code signing** do instalador
- [ ] **EULA + Política de Privacidade (LGPD)**
- [ ] Figura jurídica + emissão de **nota fiscal**

**Essenciais (qualidade de produto):**
- [ ] Instalador profissional (Inno Setup/NSIS) testado em PC limpo
- [ ] Atualização automática + crash reporting
- [ ] CI + cobertura de testes + lint
- [ ] Benchmark de desempenho no pipeline de release
- [ ] Trial/avaliação

**Desejáveis (escala e marketing):**
- [ ] Registro de marca (INPI)
- [ ] Site/landing + integração de pagamento automática
- [ ] Manual/vídeos do usuário
- [ ] Portal de cliente (gerenciar próprias ativações)

---

## 9. Fases sugeridas
1. **Fundação legal/técnica**: resolver PyMuPDF, abrir empresa, escrever EULA/privacidade.
2. **Licenciamento**: integrar serviço de licença + tela de ativação + trial.
3. **Empacotamento**: code signing + instalador + auto-update + crash reporting.
4. **Vendas**: landing + pagamento + entrega automática de chave + suporte.
5. **Endurecimento**: CI, cobertura, benchmark no release, manual do usuário.
6. **Escala**: marca, portal do cliente, marketing.

---

*Este documento é um plano vivo. Atualizar conforme as decisões (serviço de licença escolhido, regime tributário, política de preço) forem tomadas.*
