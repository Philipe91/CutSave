import { Faq } from "@/components/site/Faq"

const Check = () => (
  <svg
    className="ok"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.6"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

const PAY_LINK = "[LINK_PAGAMENTO]"
const SUPPORT = "[SUPORTE]"

function App() {
  return (
    <>
      {/* ===== HEADER ===== */}
      <header className="header">
        <div className="container nav">
          <a href="#" className="brand" aria-label="PrintNest Pro">
            <img src="/assets/printnest-logo.png" alt="PrintNest Pro" />
          </a>
          <nav className="nav-links">
            <a href="#solucao">Recursos</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#preco">Preço</a>
            <a href="#faq">Dúvidas</a>
          </nav>
          <div className="nav-cta">
            <a href="#preco" className="btn btn-primary">
              Comprar por R$ 397
            </a>
          </div>
        </div>
      </header>

      {/* ===== 1. HERO ===== */}
      <section className="hero">
        <div className="container">
          <div className="badge-row">
            <span className="pill">
              <span className="dot"></span> Licença vitalícia
            </span>
            <span className="pill">Pagamento único</span>
            <span className="pill">Windows · Offline</span>
          </div>
          <h1>
            Sua produção de impressão e corte pronta em{" "}
            <span className="accent">minutos</span>, não em horas.
          </h1>
          <p className="lead">
            O PrintNest Pro organiza suas artes no material, gera a faca de corte
            automaticamente, cria as marcas de registro e entrega tudo pronto para a sua
            impressora e para qualquer máquina de corte. Menos material no lixo, menos
            trabalho manual e mais pedidos entregues no prazo.
          </p>
          <div className="hero-actions">
            <a href="#preco" className="btn btn-primary btn-lg">
              Comprar por R$ 397
            </a>
            <a href="#como-funciona" className="btn btn-secondary btn-lg">
              Ver como funciona
            </a>
          </div>
          <p className="hero-note">
            Pagamento único · Licença vitalícia · Garantia de 7 dias
          </p>

          <figure className="app-shot">
            <div className="app-shot-bar">
              <span className="d r"></span>
              <span className="d y"></span>
              <span className="d g"></span>
              <span className="title">
                PrintNest Pro em produção: nesting e faca de corte no mesmo trabalho
              </span>
            </div>
            <img
              src="/assets/app-producao.jpg"
              alt="Tela do PrintNest Pro: peças encaixadas no material, impressão em cima e faca de corte (linha vermelha) embaixo, com aproveitamento de 77%."
            />
            <figcaption className="app-shot-cap">
              <strong>435 peças</strong> encaixadas · <strong>77%</strong> de
              aproveitamento · impressão + faca no mesmo trabalho
            </figcaption>
          </figure>
          <div className="export-chip">
            <span className="file">
              <span className="tag pdf">PDF</span> Impressão
            </span>
            <span className="file">
              <span className="tag dxf">DXF</span> Corte
            </span>
          </div>
        </div>
      </section>

      {/* ===== 2. O PROBLEMA ===== */}
      <section id="problema">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">O problema</span>
            <h2>Posicionar arte na mão custa caro</h2>
          </div>
          <p className="lead-block">
            Toda gráfica conhece essa rotina: abrir o CorelDRAW, posicionar arte por arte
            na mão, brigar por cada centímetro do material, desenhar a faca peça por peça,
            ajustar as marcas de registro e ainda torcer para nenhum erro estragar o
            material.
            <br />
            <br />
            <strong>
              Cada minuto nisso é dinheiro parado. Cada erro é material caro no lixo.
            </strong>
          </p>
        </div>
      </section>

      {/* ===== 3. A SOLUÇÃO ===== */}
      <section id="solucao" className="alt">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">A solução</span>
            <h2>Importe → Organize → Gere a faca → Exporte</h2>
            <p>Em poucos cliques. O PrintNest Pro faz a parte manual por você.</p>
          </div>
          <div className="features">
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <rect width="7" height="7" x="3" y="3" rx="1" />
                  <rect width="7" height="7" x="14" y="3" rx="1" />
                  <rect width="7" height="7" x="14" y="14" rx="1" />
                  <rect width="7" height="7" x="3" y="14" rx="1" />
                </svg>
              </div>
              <h3>Nesting automático</h3>
              <p>
                Encaixa suas peças dentro do perímetro que você define, aproveitando cada
                centímetro do material. Menos sobra, mais peças por metro.
              </p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <circle cx="6" cy="6" r="3" />
                  <path d="M8.12 8.12 12 12" />
                  <path d="M20 4 8.12 15.88" />
                  <circle cx="6" cy="18" r="3" />
                  <path d="M14.8 14.8 20 20" />
                </svg>
              </div>
              <h3>Faca automática, de verdade</h3>
              <p>
                Detecta o contorno de cada desenho e gera a linha de corte sozinho. Uma
                folha com vários desenhos? Faz a faca de cada um, pronta para o seu
                maquinário de corte.
              </p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="9" />
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v3" />
                  <path d="M12 19v3" />
                  <path d="M2 12h3" />
                  <path d="M19 12h3" />
                </svg>
              </div>
              <h3>Marcas de registro para corte preciso</h3>
              <p>
                Gera as marcas que sua máquina usa para alinhar o corte com a impressão:
                IECHO (bolinhas), Mimaki (marcas em L) ou as duas ao mesmo tempo.
              </p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <path d="M6 9V2h12v7" />
                  <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                  <rect width="12" height="8" x="6" y="14" rx="1" />
                </svg>
              </div>
              <h3>Exporta em todos os formatos</h3>
              <p>
                PDF de impressão (vetores preservados), DXF de corte para a sua máquina,
                faca em PDF e a impressão também em imagem: PNG, JPEG e PDF, no DPI que
                você escolher.
              </p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <path d="M12 3v12" />
                  <path d="m8 11 4 4 4-4" />
                  <path d="M8 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-4" />
                </svg>
              </div>
              <h3>Vários projetos ao mesmo tempo</h3>
              <p>
                Abas de trabalho estilo CorelDRAW, com os atalhos que você já conhece
                (Ctrl+C, Ctrl+V, Ctrl+D…).
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 4. POR QUE PRINTNEST ===== */}
      <section id="por-que">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Por que PrintNest</span>
            <h2>Feito para produção de verdade</h2>
          </div>
          <div className="features">
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <path d="M2 20h20" />
                  <path d="M4 20V8l6-3v15" />
                  <path d="M10 20V5l8 4v11" />
                  <path d="M14 12h.01" />
                  <path d="M14 16h.01" />
                </svg>
              </div>
              <h3>Feito para a gráfica</h3>
              <p>
                Não é um editor genérico. Cada função resolve uma dor real da produção de
                impressão digital.
              </p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <path d="M12 20h.01" />
                  <path d="M8.5 16.429a5 5 0 0 1 7 0" />
                  <path d="M5 12.859a10 10 0 0 1 5.17-2.69" />
                  <path d="M19 12.859a10 10 0 0 0-2.008-1.523" />
                  <path d="M2 8.82a15 15 0 0 1 4.177-2.643" />
                  <path d="M22 8.82a15 15 0 0 0-11.288-3.764" />
                  <path d="m2 2 20 20" />
                </svg>
              </div>
              <h3>Roda no seu PC, offline</h3>
              <p>Sem depender de internet, sem nuvem, sem mensalidade. Instala e usa.</p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z" />
                  <path d="M22 10v6" />
                  <path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5" />
                </svg>
              </div>
              <h3>Curva de aprendizado curta</h3>
              <p>Se você usa CorelDRAW, se sente em casa em minutos.</p>
            </div>
            <div className="feature">
              <div className="fi">
                <svg className="icon" viewBox="0 0 24 24">
                  <path d="M16 8h.01" />
                  <path d="M11 8a5 5 0 0 0-5 5v1a2 2 0 0 1-2 2 1 1 0 0 0 0 2h1" />
                  <path d="M19 12a3 3 0 1 0 0-6" />
                  <path d="M5 15a7 7 0 0 0 14 0v-2a7 7 0 0 0-7-7" />
                  <path d="M8 21h8" />
                </svg>
              </div>
              <h3>Economia que se paga</h3>
              <p>
                O aproveitamento de material e o tempo economizado pagam o software
                rápido.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 5. COMO FUNCIONA ===== */}
      <section id="como-funciona" className="alt">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Como funciona</span>
            <h2>Três passos, do arquivo à máquina</h2>
          </div>
          <div className="steps three">
            <div className="step">
              <div className="num">1</div>
              <h3>Importe</h3>
              <p>Arraste seus arquivos (PDF, PNG, JPG) e solte na tela.</p>
            </div>
            <div className="step">
              <div className="num">2</div>
              <h3>Gere a faca</h3>
              <p>
                Defina a quantidade e clique em Gerar Faca. O PrintNest organiza e cria o
                corte.
              </p>
            </div>
            <div className="step">
              <div className="num">3</div>
              <h3>Exporte</h3>
              <p>Impressão e faca prontas. Envie para a máquina e comece a produzir.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 6. PREÇO ===== */}
      <section id="preco">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Preço</span>
            <h2>Uma licença. Pra sempre.</h2>
          </div>
          <p className="value-anchor">
            Um único material mal aproveitado já custa mais que isso.{" "}
            <strong>O PrintNest se paga no primeiro mês</strong>, no material que você
            deixa de jogar fora e nas horas que você para de perder posicionando arte na
            mão.
          </p>
          <div className="price-wrap">
            <div className="price-card">
              <div className="kicker">PrintNest Pro</div>
              <div className="amount">R$ 397</div>
              <div className="terms">
                pagamento único · licença vitalícia · sem mensalidade
              </div>
              <ul className="feat">
                <li>
                  <Check /> Nesting automático + faca de corte automática
                </li>
                <li>
                  <Check /> Marcas de registro (IECHO, Mimaki ou as duas)
                </li>
                <li>
                  <Check /> Exporta PDF, DXF e imagem (PNG / JPEG / PDF)
                </li>
                <li>
                  <Check /> Multi-projeto em abas + atalhos estilo CorelDRAW
                </li>
                <li>
                  <Check /> Roda offline no seu PC (Windows)
                </li>
                <li>
                  <Check /> Atualizações da versão + suporte
                </li>
              </ul>
              <div className="guarantee-inline">
                <strong>Garantia incondicional de 7 dias.</strong> Comprou, testou e não
                era para você? Devolvemos 100% do seu dinheiro. Sem burocracia.
              </div>
              <a href={PAY_LINK} className="btn btn-primary btn-lg btn-block">
                Comprar por R$ 397
              </a>
              <p className="pay-line">Pague no PIX, boleto ou cartão (parcelável).</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 7. FAQ ===== */}
      <section id="faq" className="alt">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Dúvidas</span>
            <h2>Perguntas frequentes</h2>
          </div>
          <Faq />
        </div>
      </section>

      {/* ===== 8. CTA FINAL ===== */}
      <section id="comprar">
        <div className="container">
          <div className="cta">
            <h2>Pare de perder tempo e material.</h2>
            <p>
              Comece hoje a produzir mais rápido, com menos desperdício e a faca sempre
              certa.
            </p>
            <div className="hero-actions">
              <a href={PAY_LINK} className="btn btn-primary btn-lg">
                Comprar o PrintNest Pro por R$ 397
              </a>
            </div>
            <p className="hero-note" style={{ color: "#A6B7D3", marginTop: "20px" }}>
              Garantia de 7 dias · Pagamento único · Suporte incluído
            </p>
          </div>
        </div>
      </section>

      {/* ===== REQUISITOS ===== */}
      <div className="requisitos">
        <div className="container">
          <strong>Windows 10/11 · 64-bit</strong> · não requer instalação de outros
          programas · Suporte: {SUPPORT}
        </div>
      </div>

      {/* ===== FOOTER ===== */}
      <footer className="footer">
        <div className="container">
          <div className="footer-grid">
            <div className="fbrand">
              <img src="/assets/printnest-logo.png" alt="PrintNest Pro" />
              <p>
                Software de nesting e faca de corte para gráficas de comunicação visual.
                Roda offline no Windows.
              </p>
            </div>
            <div>
              <h4>Produto</h4>
              <ul>
                <li>
                  <a href="#solucao">Recursos</a>
                </li>
                <li>
                  <a href="#como-funciona">Como funciona</a>
                </li>
                <li>
                  <a href="#preco">Preço</a>
                </li>
                <li>
                  <a href="#faq">Dúvidas</a>
                </li>
              </ul>
            </div>
            <div>
              <h4>Suporte</h4>
              <ul>
                <li>
                  <a href="#faq">Dúvidas frequentes</a>
                </li>
                <li>
                  <a href={SUPPORT}>Falar com o suporte</a>
                </li>
                <li>
                  <a href="#preco">Comprar</a>
                </li>
              </ul>
            </div>
            <div>
              <h4>Legal</h4>
              <ul>
                <li>
                  <a href="#">Termos de uso (EULA)</a>
                </li>
                <li>
                  <a href="#">Política de privacidade</a>
                </li>
                <li>
                  <a href="#">Política de reembolso</a>
                </li>
              </ul>
            </div>
          </div>
          <div className="footer-bottom">
            <span>© 2026 PrintNest Pro. Todos os direitos reservados.</span>
            <span>Feito no Brasil</span>
          </div>
        </div>
      </footer>
    </>
  )
}

export default App
