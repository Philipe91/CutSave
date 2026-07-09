import { ArrowRight } from "lucide-react"
import { FRAME_URLS_HD } from "@/hooks/useImageSequence"

const PAY_LINK = "[LINK_PAGAMENTO]"

/* 1440p para telas grandes/retina; 720p leve para telas menores */
const VIDEO_SRC =
  typeof window !== "undefined" &&
  window.innerWidth * (window.devicePixelRatio || 1) > 1400
    ? "/assets/hero-loop-hd.mp4"
    : "/assets/hero-loop.mp4"

/**
 * Hero alternativo, sem scrollytelling: o vídeo roda sozinho em loop na metade
 * direita e se dissolve num degradê branco para a esquerda, onde ficam as
 * informações e os CTAs.
 */
export function HeroVideoSplit() {
  return (
    <section className="aphv-hero" id="topo">
      <div className="aphv-video" aria-hidden="true">
        <video
          src={VIDEO_SRC}
          poster={FRAME_URLS_HD[0]}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
        />
      </div>

      {/* fumaça/degradê branco na emenda entre vídeo e conteúdo */}
      <div className="aphv-smoke" aria-hidden="true" />
      <div className="aphv-fade-bottom" aria-hidden="true" />

      <div className="aphv-copy">
        <span className="ap-eyebrow">Software para impressão e corte</span>
        <h1>A plataforma inteligente de produção gráfica.</h1>
        <p>
          O PrintNest organiza centenas de arquivos no material, gera a faca de
          corte e exporta PDF de impressão + DXF prontos para a máquina. Em
          segundos, não em horas.
        </p>

        <div className="ap-actions">
          <a href={PAY_LINK} className="ap-btn ap-btn-primary">
            Comprar por R$ 397 <ArrowRight aria-hidden="true" />
          </a>
          <a href="#recursos" className="ap-btn ap-btn-outline">
            Ver recursos
          </a>
        </div>

        <div className="aphv-proof" aria-label="Destaques">
          <span>Licença vitalícia</span>
          <span>Sem mensalidade</span>
          <span>100% offline</span>
          <span>Windows 10/11</span>
        </div>
      </div>
    </section>
  )
}
