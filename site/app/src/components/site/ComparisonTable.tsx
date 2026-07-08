export function ComparisonTable() {
  return (
    <section id="comparativo" className="comparison-section">
      <div className="container">
        <div className="section-head text-center">
          <span className="eyebrow">Por que mudar agora</span>
          <h2>A diferença entre o amadorismo manual e a produção industrial</h2>
          <p className="subtitle">
            Veja lado a lado por que posicionar artes na mão impede sua gráfica de crescer e lucrar mais.
          </p>
        </div>

        <div className="comparison-card-wrapper">
          <div className="comparison-table">
            {/* Cabeçalho da Tabela */}
            <div className="comp-row comp-header">
              <div className="comp-col comp-feature">Critério da Produção</div>
              <div className="comp-col comp-manual">
                <span className="comp-badge old">MÉTODO MANUAL</span>
                <h4>CorelDRAW / Na Mão</h4>
              </div>
              <div className="comp-col comp-pro">
                <span className="comp-badge pro">AUTOMAÇÃO INDUSTRIAL</span>
                <h4>PrintNest Pro v2026</h4>
              </div>
            </div>

            {/* Linha 1 */}
            <div className="comp-row">
              <div className="comp-col comp-feature">
                <strong>Tempo de preparação de arquivo</strong>
                <span>Por cada ordem de serviço complexa</span>
              </div>
              <div className="comp-col comp-manual neg">
                <span className="comp-icon">⏱</span>
                <strong>30 a 45 minutos</strong>
                <span>Encaixando peça por peça no mouse</span>
              </div>
              <div className="comp-col comp-pro pos">
                <span className="comp-icon">⚡</span>
                <strong>Menos de 30 segundos</strong>
                <span>Cálculo algorítmico em 1 clique</span>
              </div>
            </div>

            {/* Linha 2 */}
            <div className="comp-row">
              <div className="comp-col comp-feature">
                <strong>Aproveitamento do material</strong>
                <span>Chapas de acrílico, MDF, lona e adesivos</span>
              </div>
              <div className="comp-col comp-manual neg">
                <span className="comp-icon">🗑</span>
                <strong>60% a 70% médio</strong>
                <span>Retalhos enormes jogados na caçamba</span>
              </div>
              <div className="comp-col comp-pro pos">
                <span className="comp-icon">📈</span>
                <strong>77% a 85%+ milimétrico</strong>
                <span>Encaixe de alta densidade sem lacunas</span>
              </div>
            </div>

            {/* Linha 3 */}
            <div className="comp-row">
              <div className="comp-col comp-feature">
                <strong>Faca de corte DXF / Linha de contorno</strong>
                <span>Para plotter de recorte, router ou laser</span>
              </div>
              <div className="comp-col comp-manual neg">
                <span className="comp-icon">✏</span>
                <strong>Desenhada nó por nó</strong>
                <span>Sujeita a erros de sangria e cortes duplos</span>
              </div>
              <div className="comp-col comp-pro pos">
                <span className="comp-icon">🎯</span>
                <strong>100% automática com sangria</strong>
                <span>Detecta o contorno exato e gera arquivo limpo</span>
              </div>
            </div>

            {/* Linha 4 */}
            <div className="comp-row">
              <div className="comp-col comp-feature">
                <strong>Marcas de Registro Óptico</strong>
                <span>Alinhamento entre impressão e mesa de corte</span>
              </div>
              <div className="comp-col comp-manual neg">
                <span className="comp-icon">⚠</span>
                <strong>Ajuste manual propenso a desvio</strong>
                <span>Perda de chapa inteira se sair 1mm fora</span>
              </div>
              <div className="comp-col comp-pro pos">
                <span className="comp-icon">✔</span>
                <strong>Nativo IECHO + Mimaki + Laser</strong>
                <span>Geração automática perfeita e calibrada</span>
              </div>
            </div>

            {/* Linha 5 */}
            <div className="comp-row">
              <div className="comp-col comp-feature">
                <strong>Custo de aquisição & modelo</strong>
                <span>Impacto no fluxo de caixa</span>
              </div>
              <div className="comp-col comp-manual neg">
                <span className="comp-icon">💸</span>
                <strong>Assinatura anual cara + horas perdidas</strong>
                <span>R$ 1.800+/ano em softwares genéricos</span>
              </div>
              <div className="comp-col comp-pro pos">
                <span className="comp-icon">🔒</span>
                <strong>R$ 397 único — Licença Vitalícia</strong>
                <span>Sem mensalidade, roda offline no seu Windows</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
