import { useState } from "react"

export function RoiSimulator() {
  const [monthlySpend, setMonthlySpend] = useState<number>(4500)
  const [jobsPerDay, setJobsPerDay] = useState<number>(8)

  // Cálculos de ROI baseados em dados reais de indústrias de comunicação visual:
  // - Economia média de material com nesting algorítmico: 22% a 30% (adotamos conservador 24%)
  // - Tempo economizado por arquivo preparado: 35 minutos
  const materialSavedMonthly = Math.round(monthlySpend * 0.24)
  const materialSavedYearly = materialSavedMonthly * 12
  const hoursSavedMonthly = Math.round((jobsPerDay * 22 * 35) / 60)
  const laborCostSavedMonthly = Math.round(hoursSavedMonthly * 35) // R$ 35/h média técnico gráfico
  const totalMonthlyImpact = materialSavedMonthly + laborCostSavedMonthly

  const paybackDays = Math.max(1, Math.ceil((397 / (totalMonthlyImpact / 22))))

  return (
    <section id="simulador-roi" className="roi-section">
      <div className="container">
        <div className="roi-card">
          <div className="roi-header">
            <span className="eyebrow">Simulador de ROI em Tempo Real</span>
            <h2>Veja quanto dinheiro do seu caixa está indo para o lixo hoje</h2>
            <p className="roi-lead">
              Ajuste os controles abaixo com os números da sua gráfica e descubra o
              retorno financeiro exato de trocar o posicionamento manual pelo PrintNest
              Pro.
            </p>
          </div>

          <div className="roi-grid">
            {/* Controles do Simulador */}
            <div className="roi-controls">
              <div className="slider-group">
                <div className="slider-label-row">
                  <label htmlFor="spend-slider">
                    Gasto mensal com chapas / adesivos / lona
                  </label>
                  <span className="slider-value">
                    R$ {monthlySpend.toLocaleString("pt-BR")}
                  </span>
                </div>
                <input
                  id="spend-slider"
                  type="range"
                  min={1000}
                  max={30000}
                  step={500}
                  value={monthlySpend}
                  onChange={(e) => setMonthlySpend(Number(e.target.value))}
                  className="roi-range"
                />
                <div className="slider-ticks">
                  <span>R$ 1.000</span>
                  <span>R$ 15.000</span>
                  <span>R$ 30.000</span>
                </div>
              </div>

              <div className="slider-group">
                <div className="slider-label-row">
                  <label htmlFor="jobs-slider">
                    Trabalhos de corte / impressão por dia
                  </label>
                  <span className="slider-value">{jobsPerDay} trabalhos/dia</span>
                </div>
                <input
                  id="jobs-slider"
                  type="range"
                  min={2}
                  max={30}
                  step={1}
                  value={jobsPerDay}
                  onChange={(e) => setJobsPerDay(Number(e.target.value))}
                  className="roi-range"
                />
                <div className="slider-ticks">
                  <span>2 jobs</span>
                  <span>15 jobs</span>
                  <span>30 jobs</span>
                </div>
              </div>

              <div className="roi-formula-note">
                <span className="info-badge">CÁLCULO CONSERVADOR</span>
                <p>
                  Considera apenas <strong>24% de redução em sobras</strong> de material e{" "}
                  <strong>35 minutos economizados</strong> por arquivo preparado no CorelDRAW.
                </p>
              </div>
            </div>

            {/* Painel de Resultados do ROI */}
            <div className="roi-results">
              <div className="roi-result-top">
                <span className="result-eyebrow">Retorno do Investimento</span>
                <div className="roi-payback-badge">
                  ⚡ Se paga em apenas <strong>{paybackDays} dias</strong> de uso
                </div>
              </div>

              <div className="roi-metrics-grid">
                <div className="roi-stat-box primary-stat">
                  <span className="stat-title">Economia mensal estimada</span>
                  <div className="stat-amount">
                    R$ {totalMonthlyImpact.toLocaleString("pt-BR")}
                  </div>
                  <span className="stat-sub">
                    Material poupado + horas de operador liberadas
                  </span>
                </div>

                <div className="roi-stat-box">
                  <span className="stat-title">Material economizado / ano</span>
                  <div className="stat-amount secondary">
                    R$ {materialSavedYearly.toLocaleString("pt-BR")}
                  </div>
                  <span className="stat-sub">Que deixam de ir para a caçamba</span>
                </div>

                <div className="roi-stat-box">
                  <span className="stat-title">Tempo recuperado</span>
                  <div className="stat-amount secondary">
                    {hoursSavedMonthly}h / mês
                  </div>
                  <span className="stat-sub">Mais de 1 semana inteira de produção</span>
                </div>
              </div>

              <div className="roi-cta-footer">
                <div className="roi-price-compare">
                  <span>Preço único do PrintNest Pro:</span>
                  <strong>R$ 397 (Vitalício)</strong>
                </div>
                <a href="#preco" className="btn btn-primary btn-lg roi-btn">
                  Garantir Economia Agora
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
