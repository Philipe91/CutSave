import { useEffect, useRef } from "react"

const PAY_LINK = "[LINK_PAGAMENTO]"

/**
 * Frame inicial do vídeo do hero. Quando o esquema do scroll-video chegar,
 * a sequência completa já está em /assets/hero-frames/ (51 frames).
 */
const HERO_FRAME = "/assets/hero-frames/ezgif-frame-001.jpg"

const GridIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <rect x="3" y="3" width="7" height="7" rx="2" />
    <rect x="14" y="3" width="7" height="7" rx="2" />
    <rect x="3" y="14" width="7" height="7" rx="2" />
    <rect x="14" y="14" width="7" height="7" rx="2" />
  </svg>
)

export function Hero() {
  const centerRef = useRef<HTMLDivElement>(null)
  const bgRef = useRef<HTMLDivElement>(null)

  /* Texto do hero sofre blur + fade + parallax conforme o scroll (efeito da referência) */
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (reduced) return

    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const y = window.scrollY
        const p = Math.min(1, y / (window.innerHeight * 0.66))
        if (centerRef.current) {
          centerRef.current.style.opacity = String(Math.max(0, 1 - p * 1.15))
          centerRef.current.style.filter = `blur(${(p * 14).toFixed(2)}px)`
          centerRef.current.style.transform = `translateY(${(y * 0.22).toFixed(1)}px) scale(${(1 - p * 0.05).toFixed(3)})`
        }
        if (bgRef.current) {
          bgRef.current.style.transform = `translateY(${(y * 0.1).toFixed(1)}px) scale(1.04)`
        }
      })
    }
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => {
      window.removeEventListener("scroll", onScroll)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <section className="ed-slab ed-hero" id="topo">
      <div
        ref={bgRef}
        className="ed-hero__bg"
        style={{ backgroundImage: `url(${HERO_FRAME})` }}
        aria-hidden="true"
      />

      {/* Header dentro do hero */}
      <header className="ed-header">
        <a href="#topo" className="ed-brand" aria-label="PrintNest Pro">
          <img src="/assets/printnest-symbol.png" alt="" />
          PrintNest<span className="pro">PRO</span>
        </a>

        <nav className="ed-pillnav" aria-label="Navegação principal">
          <a href="#topo" className="ed-pillnav__home" aria-label="Início">
            <GridIcon />
          </a>
          <a className="ed-pillnav__link" href="#recursos">Recursos</a>
          <a className="ed-pillnav__link" href="#como-funciona">Como funciona</a>
          <a className="ed-pillnav__link" href="#depoimentos">Resultados</a>
          <a className="ed-pillnav__link" href="#faq">Dúvidas</a>
        </nav>

        <a href="#preco" className="ed-header__cta">Comprar · R$ 397</a>
      </header>

      {/* Miolo com blur/fade no scroll */}
      <div className="ed-hero__center" ref={centerRef}>
        <span className="ed-hero__badge">
          Feito para
          <span className="mark">
            <img src="/assets/printnest-symbol.png" alt="" /> gráficas e comunicação visual
          </span>
        </span>

        <h1 className="ed-display ed-hero__title">
          Do arquivo do cliente à faca e ao nesting em segundos
        </h1>

        <p className="ed-hero__lead">
          Importe PDF ou imagem. O PrintNest gera a faca, encaixa as peças no material
          e exporta PDF de impressão + DXF de corte pronto para a máquina.
        </p>

        <div className="ed-hero__actions">
          <a href={PAY_LINK} className="ed-btn ed-btn--white ed-btn--lg">
            Comprar por R$ 397
          </a>
          <a href="#recursos" className="ed-btn ed-btn--ghost ed-btn--lg">
            Ver recursos
          </a>
        </div>

        <div className="ed-hero__proof">
          <span>Sem mensalidade</span>
          <span>100% offline</span>
          <span>Windows 10/11</span>
        </div>
      </div>

      {/* Board glass flutuante (estilo Board:CRM da referência) */}
      <div className="ed-hero__board" role="presentation">
        <div className="ed-board__head">
          <span className="ed-board__space">
            <span className="avatar">
              <img src="/assets/printnest-symbol.png" alt="" />
            </span>
            <span>
              Sua gráfica
              <small>produção de hoje</small>
            </span>
          </span>
          <span className="ed-board__title">
            Painel: <strong>Produção</strong>
          </span>
        </div>

        <div className="ed-board__grid">
          <div className="ed-board__panel">
            <div className="label">
              <span>Resumo da produção</span>
              <span>1200 × 2000 mm</span>
            </div>
            <div className="ed-board__stats">
              <span className="stat">
                <strong>435</strong>
                <span>peças</span>
              </span>
              <span className="stat">
                <strong>7</strong>
                <span>chapas</span>
              </span>
              <span className="stat green">
                <strong>77%</strong>
                <span>área utilizada</span>
              </span>
            </div>
            <div className="ed-board__money">
              R$ 0
              <span>de mensalidade, para sempre</span>
            </div>
          </div>

          <div className="ed-board__chatline">
            <div className="ed-bubble" style={{ alignSelf: "stretch" }}>
              <div className="who">
                Operador <span className="tag">#OS-2481</span>
              </div>
              <span className="muted">
                4 PDFs importados. Preciso disso cortando ainda hoje.
              </span>
            </div>
            <span className="ed-chip">⚙ Nesting automático</span>
            <div className="ed-bubble right" style={{ alignSelf: "stretch" }}>
              Encaixe pronto ✅
              <br />
              <span className="muted">
                435 peças em 7 chapas · faca DXF e marcas de registro geradas.
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
