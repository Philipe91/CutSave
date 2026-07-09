import { forwardRef, useImperativeHandle, useRef } from "react"

const PAY_LINK = "[LINK_PAGAMENTO]"

export type HeroTextHandle = {
  /** Atualiza opacidade/blur/posição de cada ato conforme o progresso 0..1 */
  update: (progress: number) => void
}

type Act = {
  /** faixa do scroll em que o ato vive */
  range: [number, number]
  /** o último ato não desaparece no fim */
  hold?: boolean
  align: "center" | "left" | "right"
}

/**
 * Roteiro dos 5 atos, sincronizado com a narrativa dos frames:
 * caos → cálculo → organização → produção → interface final.
 */
const ACTS: Act[] = [
  /* começa antes de 0 para o ato de abertura já estar visível no topo */
  { range: [-0.2, 0.13], align: "center" },
  { range: [0.17, 0.34], align: "left" },
  { range: [0.4, 0.58], align: "right" },
  { range: [0.63, 0.8], align: "center" },
  { range: [0.9, 1.0], align: "center", hold: true },
]

const clamp01 = (v: number) => Math.min(1, Math.max(0, v))

/**
 * Camada de texto cinematográfica sobre o canvas. Atualizada de forma
 * imperativa (sem re-render) para manter 60fps junto com a sequência.
 */
export const HeroText = forwardRef<HeroTextHandle>(function HeroText(_, ref) {
  const actRefs = useRef<(HTMLDivElement | null)[]>([])
  const hintRef = useRef<HTMLDivElement>(null)

  useImperativeHandle(ref, () => ({
    update(progress: number) {
      ACTS.forEach((act, i) => {
        const el = actRefs.current[i]
        if (!el) return
        const [a, b] = act.range
        const f = (progress - a) / (b - a)

        if (f < -0.02 || (f > 1.02 && !act.hold)) {
          if (el.style.visibility !== "hidden") {
            el.style.visibility = "hidden"
            el.style.opacity = "0"
          }
          return
        }

        const fadeIn = clamp01(f / 0.22)
        const fadeOut = act.hold ? 1 : clamp01((1 - f) / 0.22)
        const opacity = Math.min(fadeIn, fadeOut)
        const rise = (1 - fadeIn) * 46 - (1 - fadeOut) * 46
        const blur = (1 - opacity) * 12

        el.style.visibility = opacity <= 0.01 ? "hidden" : "visible"
        el.style.opacity = opacity.toFixed(3)
        el.style.transform = `translateY(${rise.toFixed(1)}px)`
        el.style.filter = `blur(${blur.toFixed(1)}px)`
      })

      if (hintRef.current) {
        const o = clamp01(1 - progress / 0.05)
        hintRef.current.style.opacity = o.toFixed(3)
      }
    },
  }))

  const setActRef = (i: number) => (el: HTMLDivElement | null) => {
    actRefs.current[i] = el
  }

  return (
    <div className="aph-text-layer" aria-hidden="false">
      {/* Ato 1 — abertura */}
      <div className="aph-act aph-act-center" ref={setActRef(0)}>
        <span className="aph-eyebrow">PrintNest Premium</span>
        <h1>A plataforma inteligente de produção gráfica</h1>
        <p>Organize centenas de arquivos de produção automaticamente, em segundos.</p>
      </div>

      {/* Ato 2 — o caos tem custo */}
      <div className="aph-act aph-act-left" ref={setActRef(1)}>
        <h2>Pare de desperdiçar material.</h2>
        <p>Cada espaço vazio é uma oportunidade.</p>
      </div>

      {/* Ato 3 — o motor pensando */}
      <div className="aph-act aph-act-right" ref={setActRef(2)}>
        <h2>
          Inteligência artificial.
          <br />
          Produção real.
        </h2>
        <p>
          O motor de nesting analisa cada documento, calcula o layout ideal e
          maximiza o aproveitamento do material automaticamente.
        </p>
      </div>

      {/* Ato 4 — pronto para produção */}
      <div className="aph-act aph-act-center" ref={setActRef(3)}>
        <h2>Pronto para produção.</h2>
        <p>
          Contornos de faca. Marcas de registro. Layouts otimizados.
          <br />
          Pronto para plotter, CNC e mesa de corte digital.
        </p>
      </div>

      {/* Ato 5 — assinatura final */}
      <div className="aph-act aph-act-center aph-act-final" ref={setActRef(4)}>
        <h2>
          Menos desperdício.
          <br />
          Mais produtividade.
        </h2>
        <p>PrintNest Premium.</p>
        <a href={PAY_LINK} className="ap-btn ap-btn-primary">
          Comprar por R$ 397
        </a>
      </div>

      {/* dica de scroll */}
      <div className="aph-scroll-hint" ref={hintRef}>
        <span>Role para ver</span>
        <i />
      </div>
    </div>
  )
})
