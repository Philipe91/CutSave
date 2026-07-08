import { Faq } from "@/components/site/Faq"
import { HeroShowcase } from "@/components/site/HeroShowcase"
import { RoiSimulator } from "@/components/site/RoiSimulator"
import { ComparisonTable } from "@/components/site/ComparisonTable"

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
      {/* ===== 0. TOP TRUST BAR ===== */}
      <div className="top-trust-bar">
        <div className="container">
          <span>
            ⚡ <strong>Licença Perpétua e Sem Mensalidade</strong>
          </span>
          <span className="trust-bullet">·</span>
          <span>Roda 100% Offline no Windows</span>
          <span className="trust-bullet">·</span>
          <span>Garantia Incondicional de 7 Dias ou seu Dinheiro de Volta</span>
        </div>
      </div>

      {/* ===== 1. HEADER ===== */}
      <header className="header">
        <div className="container nav">
          <a href="#" className="brand" aria-label="PrintNest Pro">
            <img src="/assets/printnest-logo.png" alt="PrintNest Pro" />
          </a>
          <nav className="nav-links">
            <a href="#comparativo">Comparativo</a>
            <a href="#simulador-roi">Calculadora de ROI</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#recursos">Recursos</a>
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

      {/* ===== 2. HERO INTERATIVO ===== */}
      <section className="hero">
        <div className="container">
          <div className="badge-row">
            <span className="pill">
              <span className="dot"></span> Licença vitalícia
            </span>
            <span className="pill">Pagamento único de R$ 397</span>
            <span className="pill">Windows · 100% Offline</span>
          </div>

          <h1>
            Sua produção de impressão e corte pronta em{" "}
            <span className="accent">segundos</span>, aproveitando cada centímetro de chapa.
          </h1>

          <p className="lead">
            O PrintNest Pro elimina o posicionamento manual no CorelDRAW, faz o nesting
            automático com até 85% de aproveitamento, gera a faca de corte DXF sem
            desenhar nó por nó e insere as marcas de registro IECHO ou Mimaki prontas para
            a máquina.
          </p>

          <div className="hero-actions">
            <a href="#preco" className="btn btn-primary btn-lg">
              Comprar Licença Vitalícia por R$ 397
            </a>
            <a href="#simulador-roi" className="btn btn-secondary btn-lg">
              Simular Economia na Minha Gráfica
            </a>
          </div>

          <p className="hero-note">
            Pagamento único · Sem mensalidades · Risco Zero com Garantia de 7 Dias
          </p>

          {/* SHOWCASE INTERATIVO EM ABAS */}
          <HeroShowcase />
        </div>
      </section>

      {/* ===== 3. BARRA DE COMPATIBILIDADE E AUTORIDADE INDUSTRIAL ===== */}
      <div className="compat-bar">
        <div className="container">
          <div className="compat-grid">
            <div className="compat-item">
              <span>✔</span> CorelDRAW & Illustrator
            </div>
            <div className="compat-item">
              <span>✔</span> Mesas IECHO & Mimaki
            </div>
            <div className="compat-item">
              <span>✔</span> Plotters de Recorte & Routers
            </div>
            <div className="compat-item">
              <span>✔</span> Vetores PDF, DXF, PNG e JPG
            </div>
            <div className="compat-item">
              <span>✔</span> Windows 10/11 64-bit
            </div>
          </div>
        </div>
      </div>

      {/* ===== 4. TABELA DE CONTRASTE: MANUAL vs. PRINTNEST PRO ===== */}
      <ComparisonTable />

      {/* ===== 5. SIMULADOR DE ROI INTERATIVO ===== */}
      <RoiSimulator />

      {/* ===== 6. COMO FUNCIONA (PIPELINE DE PRODUÇÃO EM 3 PASSOS) ===== */}
      <section id="como-funciona">
        <div className="container">
          <div className="section-head text-center">
            <span className="eyebrow">Fluxo de Trabalho Milimétrico</span>
            <h2>Do arquivo bruto à máquina cortando em 3 passos</h2>
            <p className="subtitle">
              Sem etapas complicadas ou manuais gigantes. Projetado para quem opera máquina
              e precisa de velocidade.
            </p>
          </div>

          <div className="steps three">
            <div className="step">
              <div className="num">1</div>
              <h3>Importe e Defina a Chapa</h3>
              <p>
                Arraste seus PDFs, PNGs ou vetores para a tela. Digite a largura e altura
                do seu material (acrílico, MDF, adesivo ou lona).
              </p>
            </div>
            <div className="step">
              <div className="num">2</div>
              <h3>Nesting + Faca em 1 Clique</h3>
              <p>
                O algoritmo calcula o melhor encaixe de alta densidade e traça a linha de
                corte vermelha com sangria milimetricamente ajustada.
              </p>
            </div>
            <div className="step">
              <div className="num">3</div>
              <h3>Exporte PDF e DXF Prontos</h3>
              <p>
                Envie o PDF em alta definição para a impressora e o arquivo DXF calibrado
                com marcas ópticas direto para a sua mesa de corte.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 7. BENTO GRID DE RECURSOS PRO ===== */}
      <section id="recursos" className="alt">
        <div className="container">
          <div className="section-head text-center">
            <span className="eyebrow">Arquitetura de Precisão</span>
            <h2>Por que gráficas de padrão internacional escolhem o PrintNest Pro</h2>
            <p className="subtitle">
              Cada recurso foi desenhado para eliminar desperdício financeiro e erro
              humano na produção diária.
            </p>
          </div>

          <div className="bento-grid">
            <div className="bento-card bento-large">
              <div>
                <span className="bento-badge">ALGORITMO DE ALTA DENSIDADE</span>
                <h3>Nesting automático que aproveita até 85% do material</h3>
                <p>
                  Diferente de organizadores simples em grade, o motor analisa contornos e
                  rotaciona peças milimetricamente para preencher áreas vazias. Reduza de
                  30% para menos de 15% o descarte de material caro.
                </p>
              </div>
              <div className="export-chip" style={{ marginTop: "24px" }}>
                <span className="file">
                  <span className="tag blue">ROI</span> Mais peças por metro linear
                </span>
              </div>
            </div>

            <div className="bento-card">
              <div>
                <span className="bento-badge">FACA INTELIGENTE</span>
                <h3>Geração de faca DXF real sem desenhar nó por nó</h3>
                <p>
                  Reconhece o perímetro externo de qualquer arte e traça a linha de corte
                  com offset personalizável. Zero perda de tempo na caneta bézier.
                </p>
              </div>
            </div>

            <div className="bento-card">
              <div>
                <span className="bento-badge">REGISTRO MILIMÉTRICO</span>
                <h3>Marcas nativas para IECHO, Mimaki e Laser</h3>
                <p>
                  Gera as marcas de registro exatas que o sensor óptico da sua máquina lê.
                  Acabe com o corte deslocado que inutiliza peças impressas.
                </p>
              </div>
            </div>

            <div className="bento-card bento-large">
              <div>
                <span className="bento-badge">PRODUTIVIDADE MULTI-ABA</span>
                <h3>Atalhos do CorelDRAW + Abas para vários pedidos simultâneos</h3>
                <p>
                  Trabalhe com a mesma fluidez mental que você já domina: Ctrl+C, Ctrl+V,
                  Ctrl+D e zoom de alta performance. Abra múltiplas ordens de serviço ao
                  mesmo tempo sem travar o computador.
                </p>
              </div>
              <div className="export-chip" style={{ marginTop: "24px" }}>
                <span className="file">
                  <span className="tag dxf">DXF</span> +{" "}
                  <span className="tag pdf">PDF</span> +{" "}
                  <span className="tag blue">PNG 300 DPI</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 8. CASOS DE SUCESSO B2B ===== */}
      <section id="depoimentos">
        <div className="container">
          <div className="section-head text-center">
            <span className="eyebrow">Resultados Reais na Produção</span>
            <h2>Quem opera na prática aprova a velocidade e economia</h2>
          </div>

          <div className="cases-grid">
            <div className="case-card">
              <p className="case-quote">
                &ldquo;Reduzimos o tempo de preparação de arquivos de 1 hora para 3 minutos
                por pedido. O aproveitamento de chapa subiu de 64% para 81% logo na
                primeira semana.&rdquo;
              </p>
              <div className="case-author">
                <strong>Carlos Eduardo Mendes</strong>
                <span>Diretor de Produção — Visual Print SP</span>
              </div>
            </div>

            <div className="case-card">
              <p className="case-quote">
                &ldquo;A exportação do DXF com a marca de registro IECHO sai perfeita.
                Antes a gente perdia pelo menos 2 chapas por semana por erro de alinhamento
                manual no Corel.&rdquo;
              </p>
              <div className="case-author">
                <strong>Roberto Alcantara</strong>
                <span>Operador de Router CNC & Mesa de Corte</span>
              </div>
            </div>

            <div className="case-card">
              <p className="case-quote">
                &ldquo;O software se pagou no primeiro lote de adesivos recortados. Não ter
                mensalidade foi decisivo para nós. Recomendo para toda gráfica digital.&rdquo;
              </p>
              <div className="case-author">
                <strong>Fernanda Silveira</strong>
                <span>Proprietária — Adesivos & Sign Brasil</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 9. PREÇO ANCORADO & GARANTIA INCONDICIONAL ===== */}
      <section id="preco" className="alt">
        <div className="container">
          <div className="section-head text-center">
            <span className="eyebrow">Investimento Único</span>
            <h2>Uma licença perpétua. Economia para sempre.</h2>
          </div>

          <p className="value-anchor">
            Softwares concorrentes cobram <strong>R$ 1.800 a R$ 3.500 por ano</strong> em
            assinaturas intermináveis. O PrintNest Pro custa uma única vez e{" "}
            <strong>se paga no seu primeiro mês de economia de material</strong>.
          </p>

          <div className="price-wrap">
            <div className="price-card">
              <div className="kicker">PRINTNEST PRO v2026 — LICENÇA VITALÍCIA</div>
              <div className="amount">R$ 397</div>
              <div className="terms">
                pagamento único · sem mensalidade · uso ilimitado no Windows
              </div>

              <ul className="feat">
                <li>
                  <Check /> Nesting automático de precisão (77% a 85%+)
                </li>
                <li>
                  <Check /> Geração automática de faca DXF e sangria
                </li>
                <li>
                  <Check /> Marcas de registro IECHO, Mimaki e Laser
                </li>
                <li>
                  <Check /> Exportação simultânea PDF Vetorial + DXF + Imagem
                </li>
                <li>
                  <Check /> Multi-projeto em abas com atalhos industriais
                </li>
                <li>
                  <Check /> Software 100% offline (segurança total dos seus arquivos)
                </li>
                <li>
                  <Check /> Suporte técnico dedicado + atualizações inclusas
                </li>
              </ul>

              <div className="guarantee-inline">
                <strong>🛡 Garantia incondicional de 7 dias.</strong> Instale, teste com os
                arquivos reais da sua gráfica. Se não economizar tempo e material,
                devolvemos 100% do seu dinheiro no PIX sem burocracia.
              </div>

              <a href={PAY_LINK} className="btn btn-primary btn-lg btn-block">
                Comprar Licença Vitalícia por R$ 397
              </a>

              <p className="pay-line">
                Pague no PIX com liberação imediata ou parcele no cartão.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 10. FAQ CRO (RESOLVENDO OBJEÇÕES) ===== */}
      <section id="faq">
        <div className="container">
          <div className="section-head text-center">
            <span className="eyebrow">Tire Suas Dúvidas</span>
            <h2>Perguntas frequentes de donos e operadores</h2>
          </div>
          <Faq />
        </div>
      </section>

      {/* ===== 11. CTA FINAL ===== */}
      <section id="comprar">
        <div className="container">
          <div className="cta">
            <h2>Pronto para estancar o desperdício de material na sua gráfica?</h2>
            <p>
              Adquira sua licença vitalícia hoje e comece a fechar arquivos de corte e
              impressão em menos de 30 segundos.
            </p>
            <div className="hero-actions">
              <a href={PAY_LINK} className="btn btn-primary btn-lg">
                Comprar o PrintNest Pro por R$ 397
              </a>
              <a href="#simulador-roi" className="btn btn-light btn-lg">
                Calcular Meu Retorno
              </a>
            </div>
            <p className="hero-note" style={{ color: "#A6B7D3", marginTop: "20px" }}>
              Garantia Risco Zero de 7 Dias · Pagamento Único · Liberação Rápida
            </p>
          </div>
        </div>
      </section>

      {/* ===== REQUISITOS ===== */}
      <div className="requisitos">
        <div className="container">
          <strong>Compatível com Windows 10 e Windows 11 (64-bit)</strong> · Não requer
          internet contínua para operar · Suporte Técnico: {SUPPORT}
        </div>
      </div>

      {/* ===== FOOTER ===== */}
      <footer className="footer">
        <div className="container">
          <div className="footer-grid">
            <div className="fbrand">
              <img src="/assets/printnest-logo.png" alt="PrintNest Pro" />
              <p>
                Software de precisão para nesting automático e faca de corte de comunicação
                visual. Desenvolvido para máxima economia de material e tempo.
              </p>
            </div>
            <div>
              <h4>Produto</h4>
              <ul>
                <li>
                  <a href="#comparativo">Comparativo</a>
                </li>
                <li>
                  <a href="#simulador-roi">Calculadora ROI</a>
                </li>
                <li>
                  <a href="#como-funciona">Como funciona</a>
                </li>
                <li>
                  <a href="#recursos">Recursos</a>
                </li>
              </ul>
            </div>
            <div>
              <h4>Comercial & Suporte</h4>
              <ul>
                <li>
                  <a href="#preco">Licença Vitalícia</a>
                </li>
                <li>
                  <a href="#faq">Dúvidas Frequentes</a>
                </li>
                <li>
                  <a href={SUPPORT}>Falar com o Suporte</a>
                </li>
              </ul>
            </div>
            <div>
              <h4>Legal & Garantia</h4>
              <ul>
                <li>
                  <a href="#">Garantia de 7 Dias</a>
                </li>
                <li>
                  <a href="#">Termos de Uso (EULA)</a>
                </li>
                <li>
                  <a href="#">Política de Privacidade</a>
                </li>
              </ul>
            </div>
          </div>
          <div className="footer-bottom">
            <span>© 2026 PrintNest Pro. Todos os direitos reservados.</span>
            <span>Tecnologia Industrial · Feito no Brasil</span>
          </div>
        </div>
      </footer>
    </>
  )
}

export default App
