import { useEffect } from "react"
import { Hero } from "./Hero"
import { FeatureTabs } from "./FeatureTabs"

const PAY_LINK = "[LINK_PAGAMENTO]"
const SUPPORT = "[SUPORTE]"
const PRICE_FRAME = "/assets/hero-frames/ezgif-frame-001.jpg"

const Check = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

const Cross = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
)

const Plus = () => (
  <span className="plus">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <path d="M5 12h14M12 5v14" />
    </svg>
  </span>
)

const FAQ_ITEMS = [
  {
    q: "Preciso de internet para usar?",
    a: "Não. Roda 100% no seu computador. A internet só é usada na hora de ativar a licença.",
  },
  {
    q: "O PrintNest gera as marcas de registro para o corte?",
    a: "Sim. Cria as marcas que a máquina lê para casar o corte com a impressão: bolinhas (IECHO), marcas em L (Mimaki) ou as duas ao mesmo tempo.",
  },
  {
    q: "Em quais formatos eu consigo exportar?",
    a: "PDF de impressão, DXF de corte e faca em PDF. A impressão também pode ser exportada como imagem em PNG, JPEG ou PDF, na resolução (DPI) que você definir.",
  },
  {
    q: "Funciona com a minha impressora e máquina de corte?",
    a: "Exporta em formatos padrão (PDF, DXF, faca em PDF) que praticamente todo maquinário de corte lê: plotters de recorte, routers, lasers e mesas de corte, como Mimaki, IECHO e outros.",
  },
  {
    q: "Para que serve, exatamente?",
    a: "Para qualquer produção que envolva impressão e corte: adesivos, rótulos, cartões, embalagens, displays, sinalização e muito mais. Se a peça precisa de faca de corte, o PrintNest organiza no material e gera a faca para o seu maquinário.",
  },
  {
    q: "Posso instalar em mais de um PC?",
    a: "A licença é ativada em um computador. Trocou de máquina? Desativa em um e ativa no outro.",
  },
  {
    q: "E se eu não gostar?",
    a: "Você tem 7 dias de garantia. Não gostou, devolvemos.",
  },
]

export function Landing() {
  /* Reveal on scroll: cada .reveal entra com fade + translate + blur */
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".reveal"))
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("is-in")
            io.unobserve(e.target)
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    )
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <div className="ed-page">
      {/* micro-barra do topo */}
      <div className="ed-microbar">
        <span>PrintNest Pro</span>
        <span>
          Software industrial · Feito no Brasil <span className="heart">♥</span>
        </span>
      </div>

      <Hero />

      <div style={{ height: "var(--gutter)" }} />

      <FeatureTabs />

      {/* Stats editoriais */}
      <section className="ed-slab ed-stats">
        <div className="ed-stat reveal">
          <strong>85%</strong>
          <span>de aproveitamento do material</span>
        </div>
        <div className="ed-stat reveal" style={{ ["--d" as string]: "0.08s" }}>
          <strong>30 s</strong>
          <span>do arquivo bruto à chapa fechada</span>
        </div>
        <div className="ed-stat reveal" style={{ ["--d" as string]: "0.16s" }}>
          <strong>R$ 0</strong>
          <span>de mensalidade, licença vitalícia</span>
        </div>
        <div className="ed-stat reveal" style={{ ["--d" as string]: "0.24s" }}>
          <strong>7 dias</strong>
          <span>de garantia incondicional</span>
        </div>
      </section>

      {/* Como funciona */}
      <section className="ed-slab ed-section" id="como-funciona">
        <div className="ed-section__head reveal">
          <span className="ed-kicker">Fluxo de trabalho</span>
          <h2 className="ed-title">Do arquivo bruto à máquina cortando em 3 passos</h2>
          <p>
            Sem etapas complicadas ou manuais gigantes. Projetado para quem opera
            máquina e precisa de velocidade.
          </p>
        </div>

        <div className="ed-steps">
          <div className="ed-step reveal">
            <div className="num">1</div>
            <h3>Importe e defina o material</h3>
            <p>
              Arraste seus PDFs, PNGs ou vetores para a tela. Digite a largura e a
              altura do seu material: acrílico, MDF, adesivo ou lona.
            </p>
          </div>
          <div className="ed-step reveal" style={{ ["--d" as string]: "0.1s" }}>
            <div className="num">2</div>
            <h3>Nesting + faca em 1 clique</h3>
            <p>
              O algoritmo calcula o melhor encaixe de alta densidade e traça a linha
              de corte com sangria milimetricamente ajustada.
            </p>
          </div>
          <div className="ed-step reveal" style={{ ["--d" as string]: "0.2s" }}>
            <div className="num">3</div>
            <h3>Exporte PDF e DXF prontos</h3>
            <p>
              Envie o PDF em alta definição para a impressora e o DXF calibrado com
              marcas ópticas direto para a sua mesa de corte.
            </p>
          </div>
        </div>
      </section>

      {/* Comparativo */}
      <section className="ed-slab ed-section ed-section--white" id="comparativo">
        <div className="ed-section__head reveal">
          <span className="ed-kicker">Antes e depois</span>
          <h2 className="ed-title">O fim do posicionamento manual</h2>
        </div>

        <div className="ed-compare">
          <div className="ed-compare__col bad reveal">
            <h3>Na mão, no CorelDRAW</h3>
            <ul>
              <li><Cross /> Até 1 hora posicionando artes por pedido</li>
              <li><Cross /> Faca desenhada nó por nó na caneta bézier</li>
              <li><Cross /> Corte deslocado inutiliza peças impressas</li>
              <li><Cross /> Cerca de 30% do material vira descarte</li>
              <li><Cross /> Um pedido de cada vez, retrabalho constante</li>
            </ul>
          </div>
          <div className="ed-compare__col good reveal" style={{ ["--d" as string]: "0.12s" }}>
            <h3>Com o PrintNest Pro</h3>
            <ul>
              <li><Check /> Chapa fechada em segundos, no automático</li>
              <li><Check /> Faca DXF gerada com offset personalizável</li>
              <li><Check /> Marcas de registro que o sensor da máquina lê</li>
              <li><Check /> Menos de 15% de descarte com nesting denso</li>
              <li><Check /> Vários pedidos em abas, com atalhos do Corel</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Cenários de produção */}
      <section className="ed-slab ed-section" id="depoimentos">
        <div className="ed-section__head reveal">
          <span className="ed-kicker">Onde o ganho aparece</span>
          <h2 className="ed-title">A venda fica óbvia quando a operação aperta</h2>
        </div>

        <div className="ed-quotes">
          <figure className="ed-quote reveal" style={{ margin: 0 }}>
            <p>
              Pedido grande, prazo curto: o operador importa os arquivos, define o
              material e deixa o nesting fechar a chapa sem montar peça por peça.
            </p>
            <footer>
              <strong>Menos hora parada</strong>
              <span>preparação de arquivo em segundos</span>
            </footer>
          </figure>
          <figure className="ed-quote reveal" style={{ margin: 0, ["--d" as string]: "0.1s" }}>
            <p>
              Arte complexa, contorno irregular: a faca sai com offset configurável,
              pronta para DXF, sem redesenhar tudo na caneta bézier.
            </p>
            <footer>
              <strong>Menos retrabalho</strong>
              <span>faca de corte limpa e repetível</span>
            </footer>
          </figure>
          <figure className="ed-quote reveal" style={{ margin: 0, ["--d" as string]: "0.2s" }}>
            <p>
              Impressão e corte no mesmo fluxo: o PrintNest gera PDF, DXF e marcas de
              registro para casar o material impresso com a máquina.
            </p>
            <footer>
              <strong>Menos material perdido</strong>
              <span>registro para IECHO, Mimaki e Laser</span>
            </footer>
          </figure>
        </div>
      </section>

      {/* Preço */}
      <section className="ed-slab ed-price" id="preco">
        <div className="ed-price__bg" style={{ backgroundImage: `url(${PRICE_FRAME})` }} aria-hidden="true" />
        <span className="ed-kicker reveal">PrintNest Pro · Licença vitalícia</span>
        <div className="ed-price__amount reveal" style={{ ["--d" as string]: "0.08s" }}>
          <sup>R$</sup>397
        </div>
        <p className="ed-price__terms reveal" style={{ ["--d" as string]: "0.14s" }}>
          pagamento único · sem mensalidade · uso ilimitado no Windows
        </p>

        <ul className="ed-price__feats reveal" style={{ ["--d" as string]: "0.2s" }}>
          <li><Check /> Nesting automático de precisão</li>
          <li><Check /> Faca DXF e sangria em 1 clique</li>
          <li><Check /> Registro IECHO, Mimaki e Laser</li>
          <li><Check /> Exportação PDF + DXF + imagem</li>
          <li><Check /> Multi-projeto em abas</li>
          <li><Check /> 100% offline</li>
          <li><Check /> Suporte + atualizações inclusas</li>
        </ul>

        <div className="reveal" style={{ ["--d" as string]: "0.26s" }}>
          <a href={PAY_LINK} className="ed-btn ed-btn--white ed-btn--lg">
            Comprar licença vitalícia por R$ 397
          </a>
          <p className="ed-price__guarantee">
            <strong>🛡 Garantia incondicional de 7 dias.</strong> Instale e teste com os
            arquivos reais da sua gráfica. Se não economizar tempo e material,
            devolvemos 100% no PIX, sem burocracia.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="ed-slab ed-section ed-section--white" id="faq">
        <div className="ed-section__head reveal">
          <span className="ed-kicker">Tire suas dúvidas</span>
          <h2 className="ed-title">Perguntas frequentes</h2>
        </div>
        <div className="ed-faq reveal" style={{ ["--d" as string]: "0.1s" }}>
          {FAQ_ITEMS.map((item, i) => (
            <details key={i} open={i === 0}>
              <summary>
                {item.q} <Plus />
              </summary>
              <div className="answer">{item.a}</div>
            </details>
          ))}
        </div>
      </section>

      {/* CTA final */}
      <section className="ed-slab ed-cta" id="comprar">
        <h2 className="ed-display reveal">Pronto para estancar o desperdício de material?</h2>
        <p className="reveal" style={{ ["--d" as string]: "0.08s" }}>
          Adquira sua licença vitalícia hoje e comece a fechar arquivos de corte e
          impressão em menos de 30 segundos.
        </p>
        <div className="reveal" style={{ ["--d" as string]: "0.16s" }}>
          <a href={PAY_LINK} className="ed-btn ed-btn--dark ed-btn--lg">
            Comprar o PrintNest Pro por R$ 397
          </a>
        </div>
        <p className="ed-cta__note reveal" style={{ ["--d" as string]: "0.22s" }}>
          Compatível com Windows 10 e 11 (64-bit) · Não requer internet contínua ·
          Suporte: {SUPPORT}
        </p>
      </section>

      {/* Footer */}
      <footer className="ed-footer">
        <div className="ed-footer__grid">
          <div className="ed-footer__brand">
            <img src="/assets/printnest-logo.png" alt="PrintNest Pro" style={{ height: 34, marginBottom: 14 }} />
            <p>
              Software de precisão para nesting automático e faca de corte de
              comunicação visual. Máxima economia de material e tempo.
            </p>
          </div>
          <div>
            <h4>Produto</h4>
            <ul>
              <li><a href="#recursos">Recursos</a></li>
              <li><a href="#como-funciona">Como funciona</a></li>
              <li><a href="#comparativo">Comparativo</a></li>
            </ul>
          </div>
          <div>
            <h4>Comercial &amp; Suporte</h4>
            <ul>
              <li><a href="#preco">Licença vitalícia</a></li>
              <li><a href="#faq">Dúvidas frequentes</a></li>
              <li><a href={SUPPORT}>Falar com o suporte</a></li>
            </ul>
          </div>
          <div>
            <h4>Legal &amp; Garantia</h4>
            <ul>
              <li><a href="#">Garantia de 7 dias</a></li>
              <li><a href="#">Termos de uso (EULA)</a></li>
              <li><a href="#">Política de privacidade</a></li>
            </ul>
          </div>
        </div>
        <div className="ed-footer__bottom">
          <span>© 2026 PrintNest Pro. Todos os direitos reservados.</span>
          <span>Tecnologia industrial · Feito no Brasil</span>
        </div>
      </footer>
    </div>
  )
}
