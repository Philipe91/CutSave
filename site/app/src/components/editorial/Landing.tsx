import { useEffect } from "react"
import {
  ArrowRight,
  CheckCircle2,
  Download,
  FileOutput,
  Layers3,
  MonitorDown,
  RotateCcw,
  ScanLine,
  Scissors,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  WifiOff,
} from "lucide-react"
import { HeroSequence } from "./HeroSequence"
import { HeroVideoSplit } from "./HeroVideoSplit"
import { HeroSwitcher } from "./HeroSwitcher"
import { ACTIVE_LAYOUT } from "@/hooks/useImageSequence"

const PAY_LINK = "[LINK_PAGAMENTO]"
const SUPPORT = "[SUPORTE]"

const features = [
  {
    icon: Layers3,
    title: "Nesting automático",
    text: "Centenas de peças encaixadas no material em segundos, com rotação e alta densidade.",
  },
  {
    icon: Scissors,
    title: "Faca de corte",
    text: "Contorno DXF gerado com offset configurável, sem redesenhar nó por nó.",
  },
  {
    icon: ScanLine,
    title: "Marcas de registro",
    text: "Padrões para IECHO, Mimaki e Laser, prontos para casar impressão e corte.",
  },
  {
    icon: FileOutput,
    title: "Exportação completa",
    text: "PDF de impressão, DXF de corte, faca em PDF e imagem no DPI que você definir.",
  },
  {
    icon: RotateCcw,
    title: "Recalcular em 1 clique",
    text: "Mudou quantidade, material ou sangria? Reencaixe tudo sem começar do zero.",
  },
  {
    icon: WifiOff,
    title: "Offline e em português",
    text: "Roda no Windows da sua gráfica. Internet só para ativação e suporte.",
  },
]

const steps = [
  {
    icon: UploadCloud,
    title: "Importe",
    text: "Arraste PDFs, PNGs, JPGs ou vetores para dentro do PrintNest.",
  },
  {
    icon: Sparkles,
    title: "Automatize",
    text: "Gere faca, aplique sangria, defina material e calcule o nesting.",
  },
  {
    icon: Download,
    title: "Exporte",
    text: "Leve PDF e DXF prontos para impressora, plotter, router, laser ou mesa de corte.",
  },
]

const plans = [
  {
    title: "Manual",
    price: "Horas perdidas",
    text: "O custo escondido de continuar montando arquivo peça por peça.",
    items: ["Faca desenhada na mão", "Aproveitamento no olho", "Retrabalho a cada mudança"],
    muted: true,
  },
  {
    title: "PrintNest Pro",
    price: "R$ 397",
    text: "Licença vitalícia para automatizar o preparo da produção.",
    items: ["Nesting automático", "Faca DXF + sangria", "Registro IECHO, Mimaki e Laser", "PDF + DXF + imagem"],
    featured: true,
  },
  {
    title: "Produção",
    price: "Caixa protegido",
    text: "Menos desperdício de material e mais jobs prontos no mesmo turno.",
    items: ["Sem mensalidade", "100% offline", "Suporte incluso"],
  },
]

const faqs = [
  {
    q: "O PrintNest controla minha máquina de corte?",
    a: "Não. Ele prepara os arquivos e exporta PDF + DXF. Depois você abre no software da sua plotter, router, laser ou mesa de corte.",
  },
  {
    q: "Preciso de internet para trabalhar?",
    a: "Não. O uso é offline. A internet entra para ativar a licença, receber suporte e baixar atualizações.",
  },
  {
    q: "Ele gera faca automaticamente?",
    a: "Sim. O PrintNest reconhece o contorno da arte e gera a faca com offset/sangria configurável.",
  },
  {
    q: "Quais formatos consigo exportar?",
    a: "PDF de impressão, DXF de corte, faca em PDF e imagem em PNG/JPEG/PDF com DPI configurável.",
  },
  {
    q: "E se eu não gostar?",
    a: "Você tem 7 dias de garantia. Instale, teste com arquivos reais e peça reembolso se não fizer sentido para sua gráfica.",
  },
]

function useReveal() {
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (reduced) return

    const els = Array.from(document.querySelectorAll<HTMLElement>(".ap-reveal"))
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible")
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.16, rootMargin: "0px 0px -10% 0px" }
    )

    els.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}

const Check = ({ label }: { label: string }) => (
  <li>
    <CheckCircle2 aria-hidden="true" />
    <span>{label}</span>
  </li>
)

export function Landing() {
  useReveal()

  return (
    <div className="ap-page">
      <header className="ap-header">
        <a className="ap-brand" href="#topo" aria-label="PrintNest Pro">
          <img src="/assets/printnest-symbol.png" alt="" />
          <span>PrintNest</span>
          <strong>PRO</strong>
        </a>

        <nav className="ap-nav" aria-label="Navegação principal">
          <a href="#recursos">Recursos</a>
          <a href="#sobre">Sobre</a>
          <a href="#como-funciona">Como funciona</a>
          <a href="#preco">Preço</a>
          <a href="#faq">FAQ</a>
        </nav>

        <div className="ap-header-actions">
          <a href={SUPPORT} className="ap-link">Suporte</a>
          <a href={PAY_LINK} className="ap-btn ap-btn-primary ap-btn-sm">
            Comprar
          </a>
        </div>
      </header>

      <main>
        <div id="topo">
          {ACTIVE_LAYOUT === "video" ? <HeroVideoSplit /> : <HeroSequence />}
        </div>
        <HeroSwitcher />

        <section className="ap-section" id="recursos">
          <div className="ap-container">
            <div className="ap-section-head ap-reveal">
              <span className="ap-eyebrow">Recursos principais</span>
              <h2>As ferramentas que sua produção usa todos os dias.</h2>
              <p>
                Faca, encaixe, registro e exportação reunidos em uma interface direta,
                feita para gráfica rápida, comunicação visual e corte industrial.
              </p>
            </div>

            <div className="ap-feature-grid">
              {features.map((feature, index) => {
                const Icon = feature.icon
                return (
                  <article
                    className="ap-feature-card ap-reveal"
                    style={{ ["--delay" as string]: `${index * 0.055}s` }}
                    key={feature.title}
                  >
                    <span className="ap-icon">
                      <Icon aria-hidden="true" />
                    </span>
                    <h3>{feature.title}</h3>
                    <p>{feature.text}</p>
                  </article>
                )
              })}
            </div>
          </div>
        </section>

        <section className="ap-section ap-split" id="sobre">
          <div className="ap-container ap-split-grid">
            <div className="ap-image-stack ap-reveal">
              <div className="ap-media-frame">
                <img src="/assets/prints/p1-tela-dividida.jpg" alt="PrintNest em tela dividida: adesivos impressos em cima e a faca de corte correspondente embaixo" />
              </div>
              <div className="ap-mini-panel">
                <strong>PDF + DXF</strong>
                <span>Pacote de saída pronto para produção</span>
              </div>
            </div>

            <div className="ap-copy-block ap-reveal" style={{ ["--delay" as string]: "0.08s" }}>
              <span className="ap-kicker">Track Production Activities</span>
              <h2>Saiba exatamente o que vai para impressão e o que vai para corte.</h2>
              <p>
                Em vez de alternar entre programas e refazer contornos manualmente, você
                fecha o arquivo em um fluxo único: importa, calcula, confere e exporta.
              </p>

              <div className="ap-number-list">
                <div>
                  <strong>01</strong>
                  <span>Defina material, quantidade, sangria e padrão de registro.</span>
                </div>
                <div>
                  <strong>02</strong>
                  <span>Recalcule o encaixe quando o pedido mudar, sem reconstruir o job.</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="ap-section ap-split ap-split-alt">
          <div className="ap-container ap-split-grid">
            <div className="ap-copy-block ap-reveal">
              <span className="ap-kicker">Know More About Your Material</span>
              <h2>Menos sobra, menos retrabalho e mais previsibilidade no turno.</h2>
              <p>
                O valor do PrintNest aparece na rotina: aquela arte irregular vira faca,
                aquela chapa apertada recebe nesting, e o operador exporta tudo no formato
                que a máquina espera.
              </p>
              <a href="#preco" className="ap-text-btn">
                Garantir licença <ArrowRight aria-hidden="true" />
              </a>
            </div>

            <div className="ap-dashboard-card ap-reveal" style={{ ["--delay" as string]: "0.08s" }}>
              <div className="ap-dashboard-head">
                <span>Resumo do job</span>
                <strong>#OS-2481</strong>
              </div>
              <div className="ap-progress">
                <span style={{ width: "77%" }} />
              </div>
              <div className="ap-dashboard-stats">
                <div>
                  <strong>77%</strong>
                  <span>área utilizada</span>
                </div>
                <div>
                  <strong>7</strong>
                  <span>chapas</span>
                </div>
                <div>
                  <strong>30s</strong>
                  <span>preparo</span>
                </div>
              </div>
              <ul className="ap-check-list">
                <Check label="Faca DXF gerada" />
                <Check label="Marcas ópticas aplicadas" />
                <Check label="PDF final em alta definição" />
              </ul>
            </div>
          </div>
        </section>

        <section className="ap-section" id="como-funciona">
          <div className="ap-container">
            <div className="ap-section-head ap-reveal">
              <span className="ap-eyebrow">Como funciona?</span>
              <h2>Três passos para tirar o arquivo da fila e colocar na máquina.</h2>
            </div>

            <div className="ap-steps">
              {steps.map((step, index) => {
                const Icon = step.icon
                return (
                  <article
                    className="ap-step ap-reveal"
                    style={{ ["--delay" as string]: `${index * 0.08}s` }}
                    key={step.title}
                  >
                    <div className="ap-step-number">0{index + 1}</div>
                    <span className="ap-icon ap-icon-white">
                      <Icon aria-hidden="true" />
                    </span>
                    <h3>{step.title}</h3>
                    <p>{step.text}</p>
                  </article>
                )
              })}
            </div>
          </div>
        </section>

        <section className="ap-section ap-price-section" id="preco">
          <div className="ap-container">
            <div className="ap-section-head ap-reveal">
              <span className="ap-eyebrow">Escolha o plano</span>
              <h2>O melhor plano é parar de pagar com tempo e material perdido.</h2>
              <p>Licença vitalícia por pagamento único, com garantia de 7 dias.</p>
            </div>

            <div className="ap-plan-grid">
              {plans.map((plan) => (
                <article
                  className={`ap-plan-card ap-reveal${plan.featured ? " is-featured" : ""}${plan.muted ? " is-muted" : ""}`}
                  key={plan.title}
                >
                  {plan.featured && <span className="ap-plan-badge">Mais indicado</span>}
                  <h3>{plan.title}</h3>
                  <p>{plan.text}</p>
                  <div className="ap-plan-price">{plan.price}</div>
                  <ul className="ap-check-list">
                    {plan.items.map((item) => (
                      <Check label={item} key={item} />
                    ))}
                  </ul>
                  {plan.featured ? (
                    <a href={PAY_LINK} className="ap-btn ap-btn-primary">Comprar licença</a>
                  ) : (
                    <a href="#demo" className="ap-btn ap-btn-outline">Ver fluxo</a>
                  )}
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="ap-section ap-screens" id="demo">
          <div className="ap-container">
            <div className="ap-section-head ap-reveal">
              <span className="ap-eyebrow">O software na prática</span>
              <h2>Capturas reais, direto da produção.</h2>
              <p>
                Sem mockup e sem montagem: nesting de 479 peças em 5 chapas com 94% de
                aproveitamento, faca gerada por contorno e exportação em PDF + DXF.
              </p>
            </div>

            <div className="ap-screen-showcase ap-reveal">
              <div className="ap-screen-frame">
                <img src="/assets/prints/p2-nesting-geral.jpg" alt="Nesting real no PrintNest: 479 peças em 5 chapas com 94% de área utilizada" />
              </div>
              <div className="ap-screen-strip">
                <img src="/assets/prints/p3-faca-stickers.jpg" alt="Faca de corte gerada automaticamente ao redor de cada adesivo" />
                <img src="/assets/prints/p5-exportacao.jpg" alt="Centro de Exportação: PDF de impressão, DXF de corte e faca em PDF" />
                <img src="/assets/app-producao.jpg" alt="Visão geral da produção no PrintNest" />
              </div>
            </div>
          </div>
        </section>

        <section className="ap-download">
          <div className="ap-container ap-download-grid">
            <div className="ap-reveal">
              <span className="ap-eyebrow">PrintNest Pro para Windows</span>
              <h2>Comece com os arquivos reais da sua gráfica.</h2>
              <p>
                Instale, teste o fluxo completo e compre com garantia. O risco fica do
                nosso lado.
              </p>
              <div className="ap-actions">
                <a href={PAY_LINK} className="ap-store-btn">
                  <ShieldCheck aria-hidden="true" />
                  <span>
                    Comprar com garantia
                    <strong>Licença vitalícia</strong>
                  </span>
                </a>
                <a href={SUPPORT} className="ap-store-btn ap-store-btn-light">
                  <MonitorDown aria-hidden="true" />
                  <span>
                    Falar com suporte
                    <strong>Windows 10/11</strong>
                  </span>
                </a>
              </div>
            </div>
            <div className="ap-download-art ap-reveal" style={{ ["--delay" as string]: "0.1s" }}>
              <img src="/assets/printnest-full.png" alt="Marca PrintNest Pro" />
            </div>
          </div>
        </section>

        <section className="ap-section" id="faq">
          <div className="ap-container">
            <div className="ap-section-head ap-reveal">
              <span className="ap-eyebrow">Perguntas frequentes</span>
              <h2>Antes de levar para a produção.</h2>
            </div>

            <div className="ap-faq ap-reveal">
              {faqs.map((faq, index) => (
                <details key={faq.q} open={index === 0}>
                  <summary>{faq.q}</summary>
                  <p>{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="ap-contact" id="suporte">
          <div className="ap-container ap-contact-box ap-reveal">
            <div>
              <span className="ap-eyebrow">Let's stay connected</span>
              <h2>Pronto para automatizar a preparação da produção?</h2>
              <p>Compre a licença ou fale com o suporte para tirar dúvidas antes de instalar.</p>
            </div>
            <div className="ap-actions">
              <a href={PAY_LINK} className="ap-btn ap-btn-primary">Comprar agora</a>
              <a href={SUPPORT} className="ap-btn ap-btn-outline">Falar no suporte</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="ap-footer">
        <div className="ap-container ap-footer-grid">
          <div>
            <a className="ap-brand ap-brand-dark" href="#topo">
              <img src="/assets/printnest-symbol.png" alt="" />
              <span>PrintNest</span>
              <strong>PRO</strong>
            </a>
            <p>Preparação de produção gráfica: faca, nesting e exportação PDF + DXF.</p>
          </div>
          <div>
            <h3>Produto</h3>
            <a href="#recursos">Recursos</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#demo">Demonstração</a>
          </div>
          <div>
            <h3>Comercial</h3>
            <a href="#preco">Preço</a>
            <a href="#faq">FAQ</a>
            <a href={SUPPORT}>Suporte</a>
          </div>
          <div>
            <h3>Legal</h3>
            <a href="#">Garantia</a>
            <a href="#">Termos</a>
            <a href="#">Privacidade</a>
          </div>
        </div>
        <div className="ap-footer-bottom">
          <span>© 2026 PrintNest Pro. Todos os direitos reservados.</span>
          <span>Feito no Brasil para produção gráfica.</span>
        </div>
      </footer>
    </div>
  )
}
