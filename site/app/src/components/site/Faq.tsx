import { useEffect, useRef } from "react"

const PlusIcon = () => (
  <span className="chev">
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </svg>
  </span>
)

type Item = { q: string; a: string }

const ITEMS: Item[] = [
  {
    q: "Preciso de internet para usar?",
    a: "Não. Roda 100% no seu computador. A internet só é usada na hora de ativar a licença.",
  },
  {
    q: "O PrintNest gera as marcas de registro para o corte?",
    a: "Sim. Cria as marcas que a máquina lê para casar o corte com a impressão: bolinhas (IECHO), marcas em L (Mimaki) ou as duas ao mesmo tempo.",
  },
  {
    q: "Em quais formatos eu consigo exportar?",
    a: "PDF de impressão, DXF de corte e faca em PDF. A impressão também pode ser exportada como imagem em PNG, JPEG ou PDF, na resolução (DPI) que você definir.",
  },
  {
    q: "Funciona com a minha impressora e máquina de corte?",
    a: "Exporta em formatos padrão (PDF, DXF, faca em PDF) que praticamente todo maquinário de corte lê: plotters de recorte, routers, lasers e mesas de corte, como Mimaki, IECHO e outros.",
  },
  {
    q: "Para que serve, exatamente?",
    a: "Para qualquer produção que envolva impressão e corte: adesivos, rótulos, cartões, embalagens, displays, sinalização e muito mais. Se a peça precisa de faca de corte, o PrintNest organiza no material e gera a faca para o seu maquinário, seja plotter de recorte, router, laser ou outra máquina.",
  },
  {
    q: "Posso instalar em mais de um PC?",
    a: "A licença é ativada em um computador. Trocou de máquina? Desativa em um e ativa no outro.",
  },
  {
    q: "E se eu não gostar?",
    a: "Você tem 7 dias de garantia. Não gostou, devolvemos.",
  },
]

export function Faq() {
  const firstRef = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    if (firstRef.current) firstRef.current.open = true
  }, [])

  return (
    <div className="faq">
      {ITEMS.map((item, i) => (
        <details className="faq-item" key={i} ref={i === 0 ? firstRef : undefined}>
          <summary>
            {item.q} <PlusIcon />
          </summary>
          <div className="answer">{item.a}</div>
        </details>
      ))}
    </div>
  )
}
