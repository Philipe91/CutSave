import { useState } from "react"

interface TabData {
  id: "nesting" | "faca" | "marcas"
  label: string
  badge: string
  title: string
  description: string
  stats: {
    label: string
    value: string
    highlight?: boolean
  }[]
  exportFormats: string[]
}

const TABS: TabData[] = [
  {
    id: "nesting",
    label: "1. Nesting Automático",
    badge: "77% A 85% APROVEITAMENTO",
    title: "Encaixe inteligente que reduz sobras em segundos",
    description:
      "O motor algorítmico analisa cada peça geométrica e encaixa no perímetro exato do material. O que levava 45 minutos no CorelDRAW agora leva menos de 30 segundos com aproveitamento recorde.",
    stats: [
      { label: "Peças no job", value: "435 peças" },
      { label: "Aproveitamento", value: "77.4%", highlight: true },
      { label: "Tempo de cálculo", value: "18 seg" },
    ],
    exportFormats: ["PDF Impressão Vetorial", "PNG Alta Resolução", "DPI Personalizável"],
  },
  {
    id: "faca",
    label: "2. Faca de Corte Automática",
    badge: "CONTORNO DXF PERFEITO",
    title: "Linha de corte gerada sem desenhar nó por nó",
    description:
      "Identifica o perímetro de artes complexas ou adesivos mistos e traça a linha de corte vermelha com margem (sangria/offset) milimetricamente configurável, pronta para sua mesa ou plotter.",
    stats: [
      { label: "Precisão de corte", value: "0.01 mm", highlight: true },
      { label: "Trabalho manual", value: "0 min" },
      { label: "Compatibilidade", value: "100% DXF" },
    ],
    exportFormats: ["DXF Corte Industrial", "PDF Faca Separada", "Linha com Sangria"],
  },
  {
    id: "marcas",
    label: "3. Marcas de Registro",
    badge: "IECHO · MIMAKI · LASER",
    title: "Sincronização exata entre impressão e corte",
    description:
      "Gera automaticamente as marcas ópticas exigidas por mesas de corte industriais e plotters de recorte. Elimine o erro humano de registro e pare de estragar chapa impressa na hora de cortar.",
    stats: [
      { label: "Padrões nativos", value: "IECHO + Mimaki", highlight: true },
      { label: "Alinhamento", value: "Milimétrico" },
      { label: "Desvio na mesa", value: "Zero" },
    ],
    exportFormats: ["Marcas em L", "Marcas IECHO (Bolinhas)", "Combo Híbrido"],
  },
]

export function HeroShowcase() {
  const [activeTab, setActiveTab] = useState<"nesting" | "faca" | "marcas">("nesting")
  const current = TABS.find((t) => t.id === activeTab) || TABS[0]

  return (
    <div className="hero-showcase">
      {/* Abas de navegação da demonstração */}
      <div className="showcase-tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`showcase-tab ${activeTab === tab.id ? "active" : ""}`}
          >
            <span className="tab-label">{tab.label}</span>
            <span className="tab-badge">{tab.badge}</span>
          </button>
        ))}
      </div>

      {/* Frame da interface principal */}
      <figure className="app-shot showcase-frame">
        <div className="app-shot-bar">
          <div className="window-dots">
            <span className="d r"></span>
            <span className="d y"></span>
            <span className="d g"></span>
          </div>
          <span className="title">
            PrintNest Pro v2026 — {current.title}
          </span>
          <div className="showcase-status">
            <span className="status-dot"></span>
            <span>Motor Industrial Ativo</span>
          </div>
        </div>

        <div className="showcase-visual-wrap">
          <img
            src="/assets/app-producao.jpg"
            alt={`Tela do PrintNest Pro: ${current.title}`}
            className="showcase-image"
          />

          {/* Painel de Inspecção Técnico e Métricas (Padrão Enterprise Instrument) */}
          <div className="showcase-specs">
            <div className="spec-desc">
              <h4>{current.title}</h4>
              <p>{current.description}</p>
            </div>
            <div className="spec-metrics">
              {current.stats.map((st, i) => (
                <div
                  key={i}
                  className={`spec-box ${st.highlight ? "highlight" : ""}`}
                >
                  <span className="metric-label">{st.label}</span>
                  <strong className="metric-val">{st.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <figcaption className="app-shot-cap showcase-footer">
          <div className="export-chip">
            {current.exportFormats.map((fmt, idx) => (
              <span key={idx} className="file">
                <span className="tag blue">✔</span> {fmt}
              </span>
            ))}
          </div>
          <div className="showcase-hint">
            Clique nas abas para inspecionar cada etapa técnica do fluxo de produção
          </div>
        </figcaption>
      </figure>
    </div>
  )
}
