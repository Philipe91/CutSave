import { useEffect, useRef } from "react"
import { FRAME_COUNT, useImageSequence } from "@/hooks/useImageSequence"
import { useCanvasRenderer } from "@/hooks/useCanvasRenderer"
import { HeroText, type HeroTextHandle } from "./HeroText"

/** Progresso circular do loader (r=27 → circunferência ≈ 169.6) */
const LOADER_CIRC = 2 * Math.PI * 27

/**
 * Hero scrollytelling: seção de 450vh com canvas sticky fullscreen.
 * O scroll controla a sequência de frames (caos → otimização → interface final)
 * com interpolação suave; o texto entra em 5 atos cinematográficos.
 */
export function HeroSequence() {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const loaderRef = useRef<HTMLDivElement>(null)
  const loaderRingRef = useRef<SVGCircleElement>(null)
  const loaderPctRef = useRef<HTMLSpanElement>(null)
  const textRef = useRef<HeroTextHandle>(null)

  const { images, progress: loadProgress, ready } = useImageSequence()
  const { drawFrame, resize, sampleBackground, bgColorRef } = useCanvasRenderer(
    canvasRef,
    images
  )

  /* Loader circular — atualizado sem re-render */
  useEffect(() => {
    if (loaderRingRef.current) {
      loaderRingRef.current.style.strokeDashoffset = String(
        LOADER_CIRC * (1 - loadProgress)
      )
    }
    if (loaderPctRef.current) {
      loaderPctRef.current.textContent = `${Math.round(loadProgress * 100)}%`
    }
  }, [loadProgress])

  /* Trava o scroll até todos os frames estarem decodificados */
  useEffect(() => {
    const html = document.documentElement
    if (!ready) {
      html.style.overflow = "hidden"
      return () => {
        html.style.overflow = ""
      }
    }
    html.style.overflow = ""
    if (loaderRef.current) {
      const el = loaderRef.current
      el.style.opacity = "0"
      const t = setTimeout(() => {
        el.style.display = "none"
      }, 650)
      return () => clearTimeout(t)
    }
  }, [ready])

  /* Loop principal: scroll → frame alvo → interpolação → draw + texto */
  useEffect(() => {
    if (!ready) return

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches

    resize()
    const bg = sampleBackground()
    if (wrapperRef.current) wrapperRef.current.style.background = bg

    /*
     * O scrub segue o scroll mesmo com prefers-reduced-motion: o movimento é
     * 100% controlado pelo usuário. Nesse modo só removemos a inércia (lerp),
     * indo direto ao frame alvo.
     */
    let raf = 0
    let current = 0
    let running = true

    const tick = () => {
      if (!running) return
      const wrapper = wrapperRef.current
      if (wrapper) {
        const rect = wrapper.getBoundingClientRect()
        const total = rect.height - window.innerHeight
        const scrollProgress =
          total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 0

        const target = scrollProgress * (FRAME_COUNT - 1)
        if (reduced) {
          current = target
        } else {
          current += (target - current) * 0.16
          if (Math.abs(target - current) < 0.02) current = target
        }

        drawFrame(Math.round(current))
        textRef.current?.update(scrollProgress)
      }
      raf = requestAnimationFrame(tick)
    }

    drawFrame(0, true)
    raf = requestAnimationFrame(tick)

    return () => {
      running = false
      cancelAnimationFrame(raf)
    }
  }, [ready, drawFrame, resize, sampleBackground])

  return (
    <section
      className="aph-hero"
      ref={wrapperRef}
      style={{ background: bgColorRef.current }}
      aria-label="Apresentação do PrintNest Premium"
    >
      <div className="aph-stage">
        <canvas ref={canvasRef} className="aph-canvas" />
        <HeroText ref={textRef} />
        <div className="aph-vignette" aria-hidden="true" />
      </div>

      {/* Loader premium com progresso circular */}
      <div className="aph-loader" ref={loaderRef} role="status" aria-live="polite">
        <div className="aph-loader-box">
          <svg viewBox="0 0 60 60" aria-hidden="true">
            <circle className="track" cx="30" cy="30" r="27" />
            <circle
              className="ring"
              ref={loaderRingRef}
              cx="30"
              cy="30"
              r="27"
              strokeDasharray={LOADER_CIRC}
              strokeDashoffset={LOADER_CIRC}
            />
          </svg>
          <span className="pct" ref={loaderPctRef}>
            0%
          </span>
          <span className="label">Preparando a experiência</span>
        </div>
      </div>
    </section>
  )
}
