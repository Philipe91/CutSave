import { useState } from "react"

type Tab = {
  key: string
  label: string
  sub: string
  title: string
  body: string
  cta: string
  ctaHref: string
  bubbles: { head: string; text: string }[]
}

const TABS: Tab[] = [
  {
    key: "nesting",
    label: "Nesting",
    sub: "Motor de encaixe",
    title: "Nesting",
    body:
      "O algoritmo analisa contornos e rotaciona peças milimetricamente para preencher cada área vazia do material. Aproveite até 85% da chapa e reduza o descarte de 30% para menos de 15%.",
    cta: "Ver o encaixe em ação",
    ctaHref: "#como-funciona",
    bubbles: [
      { head: "Encaixe calculado", text: "435 peças em 7 chapas · 77% de área utilizada." },
      { head: "Alta densidade", text: "Rotação automática para preencher áreas vazias." },
    ],
  },
  {
    key: "faca",
    label: "Faca de corte",
    sub: "DXF em 1 clique",
    title: "Faca de corte",
    body:
      "Reconhece o perímetro externo de qualquer arte e traça a linha de corte com offset personalizável. A faca DXF sai pronta, sem desenhar nó por nó na caneta bézier.",
    cta: "Gerar faca sem desenhar",
    ctaHref: "#como-funciona",
    bubbles: [
      { head: "Contorno detectado", text: "Offset 0,0 mm · suavização ajustável." },
      { head: "Faca pronta ✅", text: "DXF calibrado + faca em PDF para conferência." },
    ],
  },
  {
    key: "registro",
    label: "Registro",
    sub: "IECHO · Mimaki · Laser",
    title: "Registro",
    body:
      "Gera as marcas de registro exatas que o sensor óptico da sua máquina lê: bolinhas IECHO, marcas em L Mimaki ou as duas ao mesmo tempo. Acabe com o corte deslocado que inutiliza peças impressas.",
    cta: "Casar impressão e corte",
    ctaHref: "#como-funciona",
    bubbles: [
      { head: "Marcas adicionadas", text: "Padrão IECHO (bolinhas) + Mimaki (L)." },
      { head: "Sensor óptico: OK", text: "Corte alinhado com a impressão, chapa após chapa." },
    ],
  },
  {
    key: "exportacao",
    label: "Exportação",
    sub: "PDF · DXF · PNG",
    title: "Exportação",
    body:
      "Um clique e o Centro de Exportação entrega tudo: PDF vetorial em alta definição para a impressora, DXF calibrado para a mesa de corte e imagem no DPI que você definir.",
    cta: "Conhecer o Centro de Exportação",
    ctaHref: "#como-funciona",
    bubbles: [
      { head: "Pacote gerado", text: "PDF 300 DPI + DXF + faca em PDF, de uma vez." },
      { head: "Direto para a máquina", text: "Formatos que todo maquinário de corte lê." },
    ],
  },
]

export function FeatureTabs() {
  const [active, setActive] = useState(0)
  const tab = TABS[active]

  return (
    <div className="ed-row" id="recursos">
      {/* Painel de conteúdo com abas */}
      <div className="ed-slab ed-feature reveal">
        <div className="ed-tabs" role="tablist" aria-label="Recursos do PrintNest Pro">
          {TABS.map((t, i) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={i === active}
              className={`ed-tab${i === active ? " is-active" : ""}`}
              onClick={() => setActive(i)}
            >
              <strong>{t.label}</strong>
              <span>{t.sub}</span>
            </button>
          ))}
        </div>

        <div className="ed-feature__body">
          <div className="ed-feature__content ed-fade" key={tab.key}>
            <h2 className="ed-title">{tab.title}</h2>
            <p>{tab.body}</p>
            <a href={tab.ctaHref} className="ed-btn ed-btn--dark">
              {tab.cta}
            </a>
          </div>
        </div>
      </div>

      {/* Mídia com card glass flutuante */}
      <div
        className="ed-slab ed-media reveal"
        style={{ backgroundImage: "url(/assets/app-producao.jpg)", ["--d" as string]: "0.12s" }}
      >
        <div className="ed-media__glass ed-fade" key={tab.key}>
          <span className="ed-media__icons" aria-hidden="true">
            {TABS.map((t, i) => (
              <span key={t.key} className={i === active ? "on" : ""}>
                {t.label[0]}
              </span>
            ))}
          </span>
          {tab.bubbles.map((b) => (
            <div className="ed-bubble" key={b.head}>
              <div className="who">{b.head}</div>
              <span className="muted">{b.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
