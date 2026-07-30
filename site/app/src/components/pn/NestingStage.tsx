import { useEffect, useState } from "react"
import { PECAS_HERO } from "./pecas"

/* Onde cada peça pousa na chapa, em % da largura/altura da área útil.
   Não é uma grade: as linhas ficam levemente deslocadas e as peças giram um
   pouco, para o resultado parecer encaixe e não tabela. */
const POSICOES = [
  { x: 4, y: 2, w: 18, r: -4 },
  { x: 27, y: 3.5, w: 18.5, r: 3 },
  { x: 51, y: 2, w: 18, r: -2 },
  { x: 75, y: 3.5, w: 18.5, r: 5 },
  { x: 4.5, y: 33, w: 18.5, r: 4 },
  { x: 28, y: 34.5, w: 18, r: -5 },
  { x: 51.5, y: 33.5, w: 18.5, r: 2 },
  { x: 75.5, y: 34.5, w: 18, r: -3 },
  { x: 4, y: 64, w: 18, r: -2 },
  { x: 27, y: 65.5, w: 18.5, r: 6 },
  { x: 51, y: 64, w: 18, r: -4 },
  { x: 75, y: 65.5, w: 18.5, r: 2 },
]

/* De onde cada peça vem antes de encaixar (fora da chapa). */
const ENTRADAS = [
  { fx: "-160%", fy: "-70%", fr: "-22deg" },
  { fx: "40%", fy: "-190%", fr: "16deg" },
  { fx: "180%", fy: "-120%", fr: "-14deg" },
  { fx: "220%", fy: "-60%", fr: "24deg" },
  { fx: "-210%", fy: "20%", fr: "18deg" },
  { fx: "-90%", fy: "180%", fr: "-20deg" },
  { fx: "150%", fy: "170%", fr: "12deg" },
  { fx: "230%", fy: "40%", fr: "-16deg" },
  { fx: "-180%", fy: "120%", fr: "22deg" },
  { fx: "20%", fy: "210%", fr: "-18deg" },
  { fx: "170%", fy: "190%", fr: "14deg" },
  { fx: "210%", fy: "90%", fr: "-24deg" },
]

const PASSOS = [
  { texto: "Arquivos na biblioteca", corte: false },
  { texto: "Encaixando as peças", corte: false },
  { texto: "Gerando a faca", corte: true },
  { texto: "Pronto para exportar", corte: false },
]

/* Os números são os da captura real: 198 peças, 1 chapa, 88% de área usada. */
const ALVO = 88

/**
 * O hero: a chapa do PrintNest com as peças entrando, a faca desenhando pelo
 * contorno real de cada arte e o aproveitamento subindo. É o que o programa
 * faz, rodando na frente de quem visita.
 */
export function NestingStage() {
  const [fase, setFase] = useState(0)
  const [pct, setPct] = useState(0)

  useEffect(() => {
    const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (reduzido) {
      setFase(3)
      setPct(ALVO)
      return
    }

    const timers: number[] = []
    let vivo = true

    const ciclo = () => {
      if (!vivo) return
      setFase(0)
      setPct(0)
      timers.push(window.setTimeout(() => setFase(1), 400))
      timers.push(window.setTimeout(() => setFase(2), 2200))
      timers.push(
        window.setTimeout(() => {
          setFase(3)
          // o contador sobe junto com a barra
          const inicio = performance.now()
          const passo = (agora: number) => {
            if (!vivo) return
            const t = Math.min(1, (agora - inicio) / 900)
            setPct(Math.round(ALVO * (1 - Math.pow(1 - t, 3))))
            if (t < 1) requestAnimationFrame(passo)
          }
          requestAnimationFrame(passo)
        }, 3600),
      )
      timers.push(window.setTimeout(ciclo, 9500))
    }

    ciclo()
    return () => {
      vivo = false
      timers.forEach(window.clearTimeout)
    }
  }, [])

  const passo = PASSOS[fase]

  return (
    <div className="pn-hero-shot">
      <div className="pn-chapa" data-fase={fase}>
        <div className="pn-chapa-area">
          {PECAS_HERO.slice(0, POSICOES.length).map((peca, i) => {
            const pos = POSICOES[i]
            const ent = ENTRADAS[i]
            return (
              <div
                key={peca.src}
                className="pn-nest-peca"
                style={
                  {
                    left: `${pos.x}%`,
                    top: `${pos.y}%`,
                    width: `${pos.w}%`,
                    "--r": `${pos.r}deg`,
                    "--fx": ent.fx,
                    "--fy": ent.fy,
                    "--fr": ent.fr,
                    "--d": `${i * 90}ms`,
                    "--d2": `${i * 55}ms`,
                  } as React.CSSProperties
                }
              >
                <img src={peca.src} alt="" loading="eager" decoding="async" />
                <svg viewBox={`0 0 100 ${(100 * peca.ratio).toFixed(2)}`} aria-hidden="true">
                  <path d={peca.d} pathLength={100} />
                </svg>
              </div>
            )
          })}
        </div>
      </div>

      <span className={`pn-chapa-passo${passo.corte ? " is-corte" : ""}`}>
        <i />
        {passo.texto}
      </span>

      <div className="pn-chapa-hud">
        <b>
          {pct}%<span>de área usada</span>
        </b>
        <div className="pn-chapa-bar">
          <i style={{ width: `${pct}%` }} />
        </div>
        <div className="pn-chapa-linha">
          <span>198 peças</span>
          <span>1 chapa</span>
          <span>1250 mm</span>
        </div>
      </div>

      <p className="pn-chapa-legenda">
        Peças e contornos reais, extraídos das mesmas artes que o programa recortou.
      </p>
    </div>
  )
}
