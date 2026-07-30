import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowRight, Check, Circle, Maximize2, ShieldCheck } from "lucide-react"
import { NestingStage } from "./NestingStage"

/* Preencher quando o gateway e o canal de suporte estiverem definidos. */
const PAY_LINK = "[LINK_PAGAMENTO]"
const SUPPORT = "[SUPORTE]"

/* ------------------------------------------------------------------ dados */

const steps = [
  {
    title: "Importe e diga a quantidade",
    text: "Arraste PDF, PNG, JPG ou vetor para a biblioteca e digite quantas peças de cada arte o pedido pede. Em seguida informe a largura do material que vai entrar na máquina e a altura da folha, ou zero para trabalhar em rolo.",
  },
  {
    title: "Gere a faca e feche a chapa",
    text: "Escolha o tipo de faca e a sangria em milímetros. O PrintNest desenha o contorno de cada peça, distribui tudo no material e mostra peças, chapas e área usada. Se o corte precisar de marca de registro, escolha o padrão da sua máquina: IECHO, Mimaki ou laser.",
  },
  {
    title: "Exporte para a máquina",
    text: "No Centro de Exportação você marca as chapas e o formato: PDF de impressão, DXF de corte, faca em PDF ou imagem no DPI que a sua máquina pede. O arquivo sai pronto para o software que já comanda o seu equipamento.",
  },
]

const faqs = [
  {
    q: "O PrintNest controla a minha máquina de corte?",
    a: "Não, e isso é de propósito. Ele prepara o arquivo e exporta PDF de impressão, DXF de corte e faca em PDF. Quem corta continua sendo o software que acompanha a sua plotter, router, laser ou mesa. O PrintNest entra na etapa anterior, que é montar o arquivo.",
  },
  {
    q: "Ele gera a faca sozinho mesmo em arte irregular?",
    a: "Sim. O programa lê o contorno real do desenho em PNG com fundo transparente, JPG com fundo branco, PDF vetorial e recorte por cor. Você define a sangria em milímetros (para fora ou para dentro), o canto (vivo, arredondado ou chanfrado) e o nível de suavização. Se ficar um detalhe fora do lugar, dá para editar nó por nó na própria chapa.",
  },
  {
    q: "E quando o cliente já manda a faca dentro do arquivo?",
    a: "O PrintNest reconhece a linha de corte que veio no arquivo e trabalha com ela, em vez de desenhar outra por cima. Basta escolher \"Faca do cliente (vetor do PDF)\" no menu. Os outros tipos do mesmo menu são automático, retângulo (corte reto), contorno justo, contorno suave e contorno simplificado.",
  },
  {
    q: "Como eu sei quanto de material o job vai gastar?",
    a: "O painel mostra o número de peças, quantas chapas o encaixe gerou e a porcentagem de área usada, tudo antes de exportar. Na captura do topo da página são 198 peças em 1 chapa de 1250 × 2000 mm, com 88% de área usada. Mais abaixo, um job de quatro PDFs fecha 870 peças em 7 chapas com 98%.",
  },
  {
    q: "Trabalho com rolo, não com folha. Serve?",
    a: "Serve. Você informa a largura do material e deixa a altura em zero: o encaixe passa a tratar o material como rolo contínuo. Com a altura preenchida, ele fecha folha por folha e conta quantas chapas o job consome.",
  },
  {
    q: "O cliente mudou a quantidade. Preciso refazer o arquivo?",
    a: "Não. Você troca a quantidade da arte e manda organizar de novo. O encaixe se refaz por inteiro em um clique, já com as peças novas dentro.",
  },
  {
    q: "Serve para laser e router, não só para material impresso?",
    a: "Serve. O Modo Corte encaixa pelo contorno verdadeiro da peça, com giro automático, folga entre peças, margem de chapa e preenchimento de furos, que é quando a peça pequena ocupa o vazio de dentro da peça grande. Entram SVG, DXF, PDF vetorial e texto convertido em curvas. Sai DXF para a máquina ou envio direto para o CorelDRAW.",
  },
  {
    q: "Ele faz as marcas de registro que a minha máquina lê?",
    a: "Ele gera marcas nos padrões IECHO, Mimaki e laser. Você escolhe o padrão no documento e as marcas saem junto com a arte na exportação.",
  },
  {
    q: "Quais formatos consigo exportar?",
    a: "PDF de impressão, DXF de corte, faca em PDF (só as linhas de corte) e imagem em PNG ou JPG com o DPI que você definir. Dá para exportar o job inteiro de uma vez ou apenas a chapa que a máquina vai receber agora.",
  },
  {
    q: "Preciso de internet para trabalhar?",
    a: "Não. O trabalho é 100% offline e os arquivos ficam no seu computador. A internet só entra para ativar a licença, baixar atualização e falar com o suporte.",
  },
  {
    q: "Eu uso CorelDRAW. Vou ter que abandonar?",
    a: "Não. O PrintNest não é um editor de arte, é a etapa de preparação da produção. Você continua desenhando onde já desenha e, no Modo Corte, manda o resultado direto para o CorelDRAW.",
  },
  {
    q: "É mensalidade?",
    a: "Não. Pagamento único de R$ 397, licença vitalícia para uso comercial na sua gráfica. Sem renovação anual e sem cobrança por job produzido.",
  },
  {
    q: "Roda em qual Windows?",
    a: "Windows 10 e 11, 64 bits. O instalador é assinado e não pede configuração nenhuma depois: instalou, ativou, já produz.",
  },
  {
    q: "E se não for para mim?",
    a: "São 7 dias de garantia. Instale, rode os seus arquivos de verdade e feche um job inteiro. Se não servir para a sua gráfica, peça o reembolso dentro do prazo e devolvemos o valor.",
  },
]

/* As telas que passam dentro da janela do hero. Todas têm a mesma proporção
   (janela cheia do programa), então a troca não muda a altura do bloco. */
const heroSlides = [
  {
    src: "/assets/app/chapa-dividida.webp",
    label: "Impressão e corte",
    alt: "PrintNest com 198 adesivos redondos na chapa à esquerda e a faca de corte à direita",
    caption:
      "198 peças em 1 chapa de 1250 × 2000 mm, com 3 mm de espaçamento e 88% de área usada. À esquerda a impressão, à direita a faca.",
  },
  {
    src: "/assets/app/escala-dividida.webp",
    label: "Job grande",
    alt: "PrintNest com 870 peças de quatro PDFs distribuídas em 7 chapas",
    caption:
      "Quatro PDFs de várias páginas em um job só: 870 peças em 7 chapas de 1250 × 1992 mm, com 98% de área usada.",
  },
  {
    src: "/assets/app/registro-chapa.webp",
    label: "Marcas de registro",
    alt: "Chapa de banners no PrintNest com marcas de registro em círculo e o painel Registro aberto",
    caption:
      "Marcas de registro em círculos de 5 mm aplicadas na chapa, com o painel de ajuste aberto à direita.",
  },
]

/* Variantes de hero. Enquanto o Philipe não escolhe uma, todas ficam
   disponíveis pelo seletor no canto (ou por ?hero= na URL). Quando a escolha
   estiver feita, é só apagar o seletor e deixar HERO_SKINS com uma só. */
const HERO_SKINS = [
  { id: "produto", nome: "Produto", shape: "split", tone: "light" },
  { id: "aurora", nome: "Aurora", shape: "centered", tone: "dark" },
  { id: "azul", nome: "Azul", shape: "split", tone: "dark" },
  { id: "claro", nome: "Claro", shape: "centered", tone: "light" },
  { id: "branco", nome: "Branco", shape: "centered", tone: "light" },
  { id: "grade", nome: "Grade", shape: "split", tone: "light" },
] as const

type HeroSkin = (typeof HERO_SKINS)[number]

function useHeroSkin() {
  const [id, setId] = useState<string>(() => {
    if (typeof window === "undefined") return "produto"
    return new URLSearchParams(window.location.search).get("hero") ?? "produto"
  })
  const skin: HeroSkin = HERO_SKINS.find((s) => s.id === id) ?? HERO_SKINS[0]
  return { skin, setId }
}

/* --------------------------------------------------------------- helpers */

/** Abre qualquer captura marcada com data-zoom em tela cheia, com a opção de
 *  ver em tamanho real (1:1) para o cliente ler a interface. */
function useLightbox() {
  const [item, setItem] = useState<{ src: string; alt: string; caption: string } | null>(null)
  const [full, setFull] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)

  const close = useCallback(() => setItem(null), [])

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      const img = target?.closest?.("img[data-zoom]") as HTMLImageElement | null
      if (!img) return
      event.preventDefault()
      setFull(false)
      setItem({
        src: img.currentSrc || img.src,
        alt: img.alt,
        caption: img.dataset.caption ?? "",
      })
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setItem(null)
    }
    document.addEventListener("click", onClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("click", onClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [])

  useEffect(() => {
    document.body.style.overflow = item ? "hidden" : ""
    if (item) closeRef.current?.focus()
    return () => {
      document.body.style.overflow = ""
    }
  }, [item])

  return { item, close, full, setFull, closeRef }
}

function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".pn-reveal"))
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return
          e.target.classList.add("is-visible")
          io.unobserve(e.target)
        })
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" },
    )
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])
}

function useStuckHeader() {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const onScroll = () => {
      ref.current?.classList.toggle("is-stuck", window.scrollY > 40)
    }
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])
  return ref
}

/** Captura do software dentro de uma moldura de janela. */
function Frame({
  src,
  alt,
  title = "PrintNest Pro",
  eager = false,
  zoom,
}: {
  src: string
  alt: string
  title?: string
  eager?: boolean
  zoom?: string
}) {
  return (
    <div className="pn-frame">
      <div className="pn-frame-bar" aria-hidden="true">
        <i />
        <i />
        <i />
        <span>{title}</span>
      </div>
      <img
        src={src}
        alt={alt}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
        data-zoom=""
        data-caption={zoom ?? alt}
      />
    </div>
  )
}

/** Janela do hero que troca de captura sozinha. */
function HeroWindow() {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (paused) return
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % heroSlides.length)
    }, 5200)
    return () => window.clearInterval(id)
  }, [paused])

  const slide = heroSlides[index]

  return (
    <div
      className="pn-hero-shot"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="pn-frame">
        <div className="pn-frame-bar" aria-hidden="true">
          <i />
          <i />
          <i />
          <span>PrintNest Pro · {slide.label}</span>
        </div>
        <div className="pn-slides">
          {heroSlides.map((s, i) => (
            <img
              key={s.src}
              src={s.src}
              alt={i === index ? s.alt : ""}
              className={i === index ? "is-on" : ""}
              loading={i === 0 ? "eager" : "lazy"}
              decoding="async"
              aria-hidden={i === index ? undefined : true}
              data-zoom=""
              data-caption={s.caption}
            />
          ))}
        </div>
      </div>

      <div className="pn-hero-nav">
        {heroSlides.map((s, i) => (
          <button
            key={s.src}
            type="button"
            className={`pn-hero-dot${i === index ? " is-on" : ""}`}
            aria-label={`Ver ${s.label}`}
            aria-current={i === index}
            onClick={() => setIndex(i)}
          />
        ))}
        <span className="pn-hero-slide-label">
          {index + 1} de {heroSlides.length} · {slide.label}
        </span>
      </div>

      <p className="pn-hero-caption">{slide.caption}</p>
    </div>
  )
}

function Shot({
  src,
  alt,
  data,
  caption,
  title,
  onBlue = false,
}: {
  src: string
  alt: string
  data: string
  caption: string
  title?: string
  onBlue?: boolean
}) {
  return (
    <figure className={`pn-shot${onBlue ? " on-blue" : ""}`}>
      <Frame src={src} alt={alt} title={title} zoom={`${data} · ${caption}`} />
      <figcaption>
        <span className="pn-shot-data">{data}</span>
        <span className="pn-shot-cap">{caption}</span>
        <span className="pn-zoom-hint">
          <Maximize2 aria-hidden="true" size={14} /> Clique para ampliar
        </span>
      </figcaption>
    </figure>
  )
}

/** Recorte pequeno da interface (um menu, um painel) usado como prova de um
 *  detalhe citado no texto ao lado. */
function Detail({ src, alt, caption }: { src: string; alt: string; caption: string }) {
  return (
    <figure className="pn-detail">
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        data-zoom=""
        data-caption={caption}
      />
      <figcaption>{caption}</figcaption>
    </figure>
  )
}

function Spec({ items }: { items: [string, string][] }) {
  return (
    <ul className="pn-specs">
      {items.map(([k, v]) => (
        <li key={k}>
          <span className="pn-spec-key">{k}</span>
          <span>{v}</span>
        </li>
      ))}
    </ul>
  )
}

/* ---------------------------------------------------------------- pagina */

export function Landing() {
  useReveal()
  const header = useStuckHeader()
  const { item, close, full, setFull, closeRef } = useLightbox()
  const { skin, setId } = useHeroSkin()

  return (
    <div className="pn">
      <header className="pn-header" ref={header}>
        <div className="pn-container pn-header-in">
          <a className="pn-brand" href="#topo" aria-label="PrintNest Pro, início">
            <img src="/assets/printnest-symbol.png" alt="" />
            PrintNest
            <span>PRO</span>
          </a>

          <nav className="pn-nav" aria-label="Seções da página">
            <a href="#recursos">Recursos</a>
            <a href="#fluxo">Como funciona</a>
            <a href="#compatibilidade">Compatibilidade</a>
            <a href="#preco">Preço</a>
            <a href="#faq">Dúvidas</a>
          </nav>

          <div className="pn-header-cta">
            <span className="pn-header-price">R$ 397 · vitalícia</span>
            <a className="pn-btn pn-btn-sm" href={PAY_LINK}>
              Comprar licença
            </a>
          </div>
        </div>
      </header>

      <main id="topo">
        {/* ------------------------------------------------------------ hero */}
        <section
          className={`pn-hero is-${skin.shape} is-${skin.tone}`}
          data-hero={skin.id}
        >
          <div className="pn-container">
            <div className={skin.shape === "split" ? "pn-hero-grid" : undefined}>
              <div className="pn-hero-copy">
                <span className="pn-badge pn-badge-light">
                  Software para Windows 10 e 11
                </span>
                <h1>198 peças, 1 chapa, 88% de área usada.</h1>
                <p className="pn-hero-lead">
                  <strong>
                    Do arquivo do cliente à chapa fechada, sem redesenhar faca nem encaixar no olho.
                  </strong>{" "}
                  O PrintNest Pro lê o contorno real de cada arte, gera a faca com a sangria que
                  você define, distribui as peças no material e exporta o PDF de impressão junto com
                  o DXF de corte. Ele não comanda a sua máquina: entrega o arquivo pronto para ela.
                </p>
                <div className="pn-hero-actions">
                  <a className="pn-btn pn-btn-light" href={PAY_LINK}>
                    Comprar por R$ 397 <ArrowRight aria-hidden="true" />
                  </a>
                  <a className="pn-btn pn-btn-outline-light" href="#recursos">
                    Ver o software por dentro
                  </a>
                </div>
                <p className="pn-trust">
                  Pagamento único · Licença vitalícia · Garantia de 7 dias · Trabalha offline
                </p>
              </div>

              {skin.id === "produto" ? <NestingStage /> : <HeroWindow />}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------ antes/depois */}
        <section className="pn-section">
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge">O gargalo não é a impressão</span>
              <h2>O tempo some antes de a máquina ligar.</h2>
              <p>
                Entre receber a arte do cliente e mandar para a produção existe uma etapa que ninguém
                cobra e todo mundo paga: montar o arquivo. Desenhar a faca, girar peça, fechar a
                chapa, conferir a marca de registro. O PrintNest ocupa exatamente esse espaço, entre
                o seu editor e a sua máquina.
              </p>
            </div>

            <div className="pn-compare pn-reveal">
              <div className="pn-compare-col is-before">
                <h3>Do jeito manual</h3>
                <ul>
                  <li>
                    <Circle aria-hidden="true" />
                    <span>Faca desenhada nó por nó, arte por arte, e refeita quando a arte muda.</span>
                  </li>
                  <li>
                    <Circle aria-hidden="true" />
                    <span>Peças arrastadas no olho até parecer que couberam na chapa.</span>
                  </li>
                  <li>
                    <Circle aria-hidden="true" />
                    <span>Sobra de material que só aparece depois que a chapa já foi impressa.</span>
                  </li>
                  <li>
                    <Circle aria-hidden="true" />
                    <span>Cliente dobra a quantidade e o arquivo volta para o começo.</span>
                  </li>
                  <li>
                    <Circle aria-hidden="true" />
                    <span>Marca de registro montada na mão, job por job, torcendo para o corte casar.</span>
                  </li>
                </ul>
              </div>

              <div className="pn-compare-col is-after">
                <h3>Com o PrintNest</h3>
                <ul>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Faca gerada pelo contorno real, com sangria, cantos e suavização que você define.</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Encaixe automático, girando as peças, com a área usada em porcentagem na tela.</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Você vê quantas chapas o job consome antes de qualquer coisa ir para a impressora.</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Mudou a quantidade? Um clique reorganiza a produção inteira.</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Marcas de registro no padrão IECHO, Mimaki ou laser, geradas pelo programa.</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* --------------------------------------------------------- recursos */}
        <section id="recursos" className="pn-section" style={{ paddingBottom: 0 }}>
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge pn-badge-cut">O software por dentro</span>
              <h2>Cinco ferramentas, todas as capturas reais.</h2>
              <p>
                Nada de mockup. As imagens abaixo saíram da versão que você instala, rodando arquivos
                de produção de verdade. Os números das legendas são os que o próprio programa mostrou
                na tela.
              </p>
            </div>

            {/* 1. faca */}
            <article className="pn-feature">
              <div className="pn-feature-copy pn-reveal">
                <span className="pn-badge">Faca de corte</span>
                <h2>O contorno acompanha o desenho, não a caixa dele.</h2>
                <p>
                  O PrintNest identifica a silhueta da arte e desenha a linha de corte em volta dela,
                  com a sangria que você escolher em milímetros. Funciona com PNG de fundo
                  transparente, JPG de fundo branco, PDF vetorial e recorte por cor. Se o cliente já
                  mandou a faca dentro do arquivo, o programa reconhece aquela linha e trabalha com
                  ela em vez de inventar outra. Em arte irregular, como a lua da captura abaixo, o
                  contorno entra na parte côncava do desenho. E quando ainda falta um ajuste fino,
                  você edita nó por nó na própria chapa.
                </p>
                <Detail
                  src="/assets/app/menu-tipos-faca.webp"
                  alt="Menu Gerar Faca aberto no PrintNest com os seis tipos de faca disponíveis"
                  caption="Os seis tipos ficam em um menu só, ao lado do botão Gerar Faca."
                />
              </div>
              <div className="pn-reveal" style={{ ["--delay" as string]: "0.08s" }}>
                <Spec
                  items={[
                    ["Tipos", "Automático, retângulo, contorno justo, contorno suave, contorno simplificado e a faca do cliente"],
                    ["Origem", "PNG com transparência, JPG com fundo branco, PDF vetorial e recorte por cor"],
                    ["Sangria", "Offset externo ou interno, em milímetros"],
                    ["Cantos", "Vivo, arredondado ou chanfrado, com nível de suavização"],
                    ["Ajuste fino", "Edição nó por nó, direto na chapa"],
                    ["Saída", "A mesma faca vira DXF de corte e faca em PDF"],
                  ]}
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.14s" }}>
                <Shot
                  src="/assets/app/faca.webp"
                  alt="Aproximação da área de trabalho do PrintNest mostrando a linha de corte vermelha acompanhando o contorno de cada adesivo"
                  title="PrintNest Pro · impressão + corte"
                  data="offset +2,0 mm · contorno justo · impressão + corte"
                  caption="A linha vermelha é a faca gerada pelo contorno. Ela sai em DXF e em PDF."
                />
              </div>
            </article>

            {/* 2. nesting */}
            <article className="pn-feature">
              <div className="pn-feature-copy pn-reveal">
                <span className="pn-badge">Nesting</span>
                <h2>Ele fecha a chapa e mostra quanta área foi usada.</h2>
                <p>
                  Você informa a largura do material, a altura da folha (ou zero, para rolo
                  contínuo), o espaçamento entre as peças e a quantidade de cada arte. O PrintNest
                  distribui tudo, gira o que precisa girar, quebra o job em quantas chapas forem
                  necessárias e mostra a porcentagem de área usada no painel, antes de qualquer coisa
                  ir para a impressora. A conta de material deixa de ser chute na hora de fechar o
                  pedido: 198 peças em 1 chapa na captura do topo, e 870 peças em 7 chapas na captura
                  aqui embaixo, que veio de quatro PDFs de várias páginas jogados juntos na
                  biblioteca.
                </p>
              </div>
              <div className="pn-reveal" style={{ ["--delay" as string]: "0.08s" }}>
                <Spec
                  items={[
                    ["Material", "Largura e altura livres. Altura zero trabalha em rolo contínuo"],
                    ["Entrada", "Vários arquivos no mesmo job, inclusive PDF de várias páginas"],
                    ["Espaçamento", "Folga horizontal e vertical em milímetros, com a peça centralizada na chapa"],
                    ["Giro", "O programa gira as peças que precisam girar para fechar a chapa"],
                    ["Na tela", "Peças, chapas e porcentagem de área usada, sempre à vista"],
                    ["Refazer", "Mudou o pedido, um clique reorganiza a produção inteira"],
                  ]}
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.14s" }}>
                <Shot
                  src="/assets/app/escala-dividida.webp"
                  alt="PrintNest com 870 peças de quatro PDFs distribuídas em 7 chapas, impressão em cima e faca embaixo"
                  title="PrintNest Pro · tela dividida (impressão / corte)"
                  data="4 arquivos · 870 peças · 7 chapas · 1250 × 1992 mm · 98% de área usada"
                  caption="Quatro PDFs de várias páginas em um job só. Em cima a impressão, embaixo a faca de cada chapa."
                />
              </div>
            </article>
          </div>
        </section>

        {/* 3. marcas de registro */}
        <section className="pn-section" style={{ paddingBottom: 0 }}>
          <div className="pn-container">
            <article className="pn-feature">
              <div className="pn-feature-copy pn-reveal">
                <span className="pn-badge">Marcas de registro</span>
                <h2>A marca que a sua máquina procura, no padrão dela.</h2>
                <p>
                  De nada adianta a faca estar certa se o leitor da máquina não encontrar a
                  referência. O PrintNest gera as marcas junto com a chapa, no tipo que o seu
                  equipamento lê, e deixa você ajustar afastamento, tamanho e espessura do traço em
                  milímetros. As marcas saem na exportação, tanto no PDF de impressão quanto no
                  arquivo de corte.
                </p>
                <Detail
                  src="/assets/app/menu-registro.webp"
                  alt="Painel Registro do PrintNest com a lista de tipos de marca disponíveis"
                  caption="Sete opções de registro na aba Registro do documento."
                />
              </div>
              <div className="pn-reveal" style={{ ["--delay" as string]: "0.08s" }}>
                <Spec
                  items={[
                    ["Tipos", "Círculos, marcas em L, círculos + L, quadrados, cruzes e L de canto"],
                    ["Máquinas", "Padrões usados por IECHO, Mimaki e mesas de corte a laser"],
                    ["Afastamento", "Distância da marca até a arte, em milímetros"],
                    ["Tamanho", "Diâmetro ou lado da marca e espessura do traço"],
                    ["Saída", "As marcas acompanham a chapa na exportação"],
                  ]}
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.14s" }}>
                <Shot
                  src="/assets/app/registro-chapa.webp"
                  alt="Chapa de banners no PrintNest com marcas de registro em círculo e o painel Registro aberto à direita"
                  title="PrintNest Pro · aba Registro"
                  data="18 peças · 1 chapa · 79% de área usada · registro em círculos de 5 mm"
                  caption="O painel da direita controla tipo, afastamento, tamanho e espessura da marca."
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.18s" }}>
                <Shot
                  src="/assets/app/registro-saida.webp"
                  alt="Arquivos exportados pelo PrintNest: chapas com marcas em L nos cantos e as facas de corte correspondentes"
                  title="Arquivos exportados"
                  data="faca em PDF · chapa impressa com marcas em L"
                  caption="O que sai do programa: a faca sozinha para o corte e a chapa com as marcas nos cantos."
                />
              </div>
            </article>
          </div>
        </section>

        {/* 3. modo corte, na faixa azul */}
        <section className="pn-band pn-section">
          <div className="pn-container">
            <article className="pn-feature">
              <div className="pn-feature-copy pn-reveal">
                <span className="pn-badge pn-badge-light">Modo Corte</span>
                <h2>Laser e CNC encaixam pelo contorno real, não pelo retângulo.</h2>
                <p>
                  Quem corta acrílico, MDF, ACM ou letra caixa não tem peça quadrada. O Modo Corte
                  trata cada corpo pela forma verdadeira: gira as peças, respeita a folga entre elas
                  e a margem da chapa, e ainda encaixa peça pequena dentro do vazio da peça grande.
                  Entram SVG, DXF, PDF vetorial e texto convertido em curvas. Sai DXF para a sua
                  máquina, ou o bloco volta direto para o CorelDRAW. E se você quiser mudar alguma
                  peça de lugar depois do encaixe, é só arrastar: a tecla R gira a peça selecionada.
                </p>
                <Detail
                  src="/assets/app/corte-furos.webp"
                  alt="Aproximação do Modo Corte mostrando letras encaixadas dentro do vazio de outras peças"
                  caption="Preencher furos: as letras menores ocupam o vazio de dentro das maiores."
                />
              </div>
              <div className="pn-reveal" style={{ ["--delay" as string]: "0.08s" }}>
                <Spec
                  items={[
                    ["Entrada", "SVG, DXF, PDF vetorial e texto convertido em curvas"],
                    ["Chapa", "Largura e altura da folha, folga entre peças e margem de chapa"],
                    ["Giro", "De ângulo travado a giro muito fino, de 15 em 15 graus"],
                    ["Furos", "A peça pequena ocupa o vazio de dentro da peça grande"],
                    ["Ajuste", "Arraste a peça depois do encaixe; R gira a selecionada"],
                    ["Saída", "DXF para a máquina ou envio direto para o CorelDRAW"],
                  ]}
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.14s" }}>
                <Shot
                  onBlue
                  src="/assets/app/corte-192.webp"
                  alt="Diálogo Modo Corte do PrintNest com 192 corpos de letra encaixados pelo contorno em uma única chapa"
                  title="PrintNest Pro · Modo Corte (laser / CNC)"
                  data="192 corpos · 1 chapa · bloco 991 × 1325 mm · 98% da chapa · folga 2 mm"
                  caption="192 corpos de letra em uma chapa só, com giro fino de 15 graus e 10 segundos de otimização."
                />
              </div>
            </article>
          </div>
        </section>

        {/* 4. exportacao */}
        <section className="pn-section" style={{ paddingBottom: 0 }}>
          <div className="pn-container">
            <article className="pn-feature">
              <div className="pn-feature-copy pn-reveal">
                <span className="pn-badge">Centro de Exportação</span>
                <h2>Escolhe a chapa, escolhe o formato, exporta.</h2>
                <p>
                  É a tela onde o trabalho é fechado. Ela lista as chapas do job com miniatura e
                  medida, mostra a pré-visualização do que vai sair e pede só duas decisões: quais
                  chapas e qual formato. Dá para gravar o job inteiro de uma vez ou apenas a chapa
                  que a máquina vai receber agora, sem precisar montar um arquivo separado para isso.
                </p>
              </div>
              <div className="pn-reveal" style={{ ["--delay" as string]: "0.08s" }}>
                <Spec
                  items={[
                    ["PDF de impressão", "A chapa montada, pronta para a impressora"],
                    ["DXF de corte", "Contornos posicionados para plotter, router, laser e mesa"],
                    ["Faca em PDF", "Só as linhas de corte, para conferência ou para o operador"],
                    ["Imagem", "PNG ou JPG no DPI que você definir"],
                    ["Seleção", "Todas as chapas do job ou só as que você marcar"],
                  ]}
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.14s" }}>
                <Shot
                  src="/assets/app/exportacao.webp"
                  alt="Centro de Exportação do PrintNest com a lista de chapas, pré-visualização e os quatro formatos de saída"
                  title="PrintNest Pro · Centro de Exportação"
                  data="chapa 1250 × 2381 mm · 4 formatos de saída · por chapa ou job inteiro"
                  caption="A medida da chapa e o conteúdo aparecem antes de gravar o arquivo."
                />
              </div>
            </article>
          </div>
        </section>

        {/* galeria: as demais telas, cada uma com o que ela mostra */}
        <section className="pn-section">
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge">Mais telas</span>
              <h2>Outros momentos do mesmo trabalho.</h2>
              <p>
                As capturas acima mostram o resultado. Estas mostram como ele aparece durante o
                serviço, em jobs diferentes.
              </p>
            </div>

            <div className="pn-gallery pn-reveal">
              <figure>
                <img
                  src="/assets/app/chapa-cheia.webp"
                  alt="Chapa do PrintNest com 198 adesivos redondos e a faca vermelha sobre cada peça"
                  loading="lazy"
                  decoding="async"
                  data-zoom=""
                  data-caption="198 peças com a faca desenhada por cima da arte, para conferir antes de exportar."
                />
                <figcaption>
                  <strong>Impressão e corte na mesma vista</strong>
                  198 peças com a faca desenhada por cima da arte, para conferir antes de exportar.
                </figcaption>
              </figure>
              <figure>
                <img
                  src="/assets/app/faca-circular.webp"
                  alt="Aproximação de adesivos redondos com a linha de corte circular ao redor de cada um"
                  loading="lazy"
                  decoding="async"
                  data-zoom=""
                  data-caption="De perto dá para ver a linha de corte acompanhando a borda de cada peça."
                />
                <figcaption>
                  <strong>Zoom na faca</strong>
                  De perto dá para ver a linha de corte acompanhando a borda de cada peça.
                </figcaption>
              </figure>
              <figure>
                <img
                  src="/assets/app/escala-chapa.webp"
                  alt="Sete chapas do PrintNest lado a lado com 870 peças no total"
                  loading="lazy"
                  decoding="async"
                  data-zoom=""
                  data-caption="As 7 chapas do job de 870 peças, na vista de impressão, com 98% de área usada."
                />
                <figcaption>
                  <strong>O job inteiro de uma vez</strong>
                  As 7 chapas do job de 870 peças, na vista de impressão, com 98% de área usada.
                </figcaption>
              </figure>
              <figure>
                <img
                  src="/assets/app/corte-48.webp"
                  alt="Diálogo Modo Corte do PrintNest com 48 corpos encaixados e os parâmetros de material à direita"
                  loading="lazy"
                  decoding="async"
                  data-zoom=""
                  data-caption="48 corpos em 1 chapa de 1000 × 500 mm, com margem de 5 mm e folga de 2 mm."
                />
                <figcaption>
                  <strong>Modo Corte, job menor</strong>
                  48 corpos em 1 chapa de 1000 × 500 mm, com margem de 5 mm e folga de 2 mm.
                </figcaption>
              </figure>
              <figure className="is-wide">
                <img
                  src="/assets/app/corte-ajuste.webp"
                  alt="Peça sendo arrastada dentro do Modo Corte depois do encaixe automático"
                  loading="lazy"
                  decoding="async"
                  data-zoom=""
                  data-caption="Depois do encaixe automático você arrasta a peça que quiser e gira com a tecla R."
                />
                <figcaption>
                  <strong>Ajuste na mão</strong>
                  Depois do encaixe automático você arrasta a peça que quiser e gira com a tecla R.
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* -------------------------------------------------------- CorelDRAW */}
        <section id="corel" className="pn-section" style={{ paddingTop: 0 }}>
          <div className="pn-container">
            <article className="pn-feature">
              <div className="pn-feature-copy pn-reveal">
                <span className="pn-badge">Integração com o CorelDRAW</span>
                <h2>Você nem precisa sair do Corel.</h2>
                <p>
                  A instalação coloca os comandos do PrintNest nas macros do CorelDRAW. Com o
                  desenho aberto, você manda a página inteira, só a seleção, ou abre o Modo Corte
                  direto de lá. O programa recebe o material já pronto para gerar a faca e fechar a
                  chapa, e no Modo Corte o bloco encaixado volta para o Corel pelo botão
                  Enviar p/ Corel. Nada de exportar em uma pasta, procurar o arquivo e importar de
                  novo a cada job.
                </p>
              </div>
              <div className="pn-reveal" style={{ ["--delay" as string]: "0.08s" }}>
                <Spec
                  items={[
                    ["Abrir", "Abre o PrintNest a partir do Corel"],
                    ["Enviar página", "Manda a página atual do desenho para a produção"],
                    ["Enviar seleção", "Manda só o que estiver selecionado na tela"],
                    ["Modo Corte", "Abre o encaixe de laser e CNC com o desenho já dentro"],
                    ["Volta", "O bloco encaixado retorna para o Corel pelo Enviar p/ Corel"],
                  ]}
                />
              </div>
              <div className="pn-feature-wide pn-reveal" style={{ ["--delay" as string]: "0.14s" }}>
                <Shot
                  src="/assets/app/plugin-corel.webp"
                  alt="Janela Executar macro do CorelDRAW com os comandos do PrintNest instalados"
                  title="CorelDRAW · Executar macro"
                  data="6 comandos do PrintNest instalados nas macros do Corel"
                  caption="Abrir, enviar página, enviar arquivo, enviar seleção, Modo Corte e o menu do PrintNest."
                />
              </div>
            </article>
          </div>
        </section>

        {/* ----------------------------------------------------------- fluxo */}
        <section id="fluxo" className="pn-section">
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge">Como funciona</span>
              <h2>Três passos, sempre na mesma ordem.</h2>
              <p>
                O caminho é o mesmo para adesivo, rótulo, imã, placa ou letra caixa. Muda o material
                e a máquina do fim, não o jeito de montar o arquivo.
              </p>
            </div>
            <ol className="pn-steps pn-reveal">
              {steps.map((s, i) => (
                <li className="pn-step" key={s.title}>
                  <span className="pn-step-n">0{i + 1}</span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* -------------------------------------------------- compatibilidade */}
        <section id="compatibilidade" className="pn-section" style={{ paddingTop: 0 }}>
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge">Compatibilidade</span>
              <h2>Ele se encaixa no parque que você já tem.</h2>
              <p>
                O PrintNest não substitui a sua máquina nem o seu editor de arte, e não comanda o
                equipamento. Ele fica no meio do caminho: recebe o arquivo do cliente, prepara a
                produção e devolve o formato que a impressora, a máquina de corte e o Corel esperam
                receber.
              </p>
            </div>

            <div className="pn-cols pn-reveal">
              <div className="pn-col">
                <h3>Entra</h3>
                <ul>
                  <li>PDF vetorial e PDF de imagem</li>
                  <li>PNG com fundo transparente</li>
                  <li>JPG com fundo branco e WEBP</li>
                  <li>SVG e DXF, no Modo Corte</li>
                  <li>Texto convertido em curvas</li>
                  <li>Faca já desenhada no arquivo do cliente</li>
                </ul>
              </div>
              <div className="pn-col">
                <h3>Sai</h3>
                <ul>
                  <li>PDF de impressão da chapa montada</li>
                  <li>DXF de corte</li>
                  <li>Faca em PDF, só as linhas</li>
                  <li>PNG ou JPG no DPI que você definir</li>
                  <li>Chapa avulsa ou job inteiro</li>
                  <li>Envio direto para o CorelDRAW</li>
                </ul>
              </div>
              <div className="pn-col">
                <h3>Máquinas e sistema</h3>
                <ul>
                  <li>Marcas de registro IECHO</li>
                  <li>Marcas de registro Mimaki</li>
                  <li>Marcas para laser</li>
                  <li>Plotter de recorte, router e mesa de corte</li>
                  <li>Windows 10 e 11, 64 bits</li>
                  <li>Uso offline, com instalador assinado</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------- preco */}
        <section id="preco" className="pn-section" style={{ paddingTop: 0 }}>
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge">Licença</span>
              <h2>Paga uma vez. É sua.</h2>
              <p>
                R$ 397 em pagamento único, licença vitalícia para uso comercial na sua gráfica. Sem
                mensalidade, sem renovação anual e sem cobrança por job produzido. O que você compra
                hoje é o programa completo, não uma versão reduzida.
              </p>
            </div>

            <div className="pn-price pn-reveal">
              <div className="pn-price-main">
                <span className="pn-badge">PrintNest Pro para Windows</span>
                <div className="pn-price-value">
                  R$ 397 <small>pagamento único</small>
                </div>
                <ul className="pn-price-list">
                  <li>
                    <Check aria-hidden="true" />
                    <span>Licença vitalícia para uso comercial, sem mensalidade</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>
                      Faca automática: contorno justo, retangular, círculo, oval e a faca do cliente
                    </span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Nesting com giro das peças, rolo contínuo e área usada em porcentagem</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Modo Corte para laser e CNC, com preenchimento de furos e saída em DXF</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Marcas de registro IECHO, Mimaki e laser</span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>
                      Exportação em PDF de impressão, DXF, faca em PDF e imagem com DPI configurável
                    </span>
                  </li>
                  <li>
                    <Check aria-hidden="true" />
                    <span>Atualizações e suporte em português</span>
                  </li>
                </ul>
                <a className="pn-btn pn-btn-primary" href={PAY_LINK}>
                  Comprar por R$ 397 <ArrowRight aria-hidden="true" />
                </a>
              </div>

              <div className="pn-price-side">
                <div className="pn-guarantee">
                  <strong>7 dias de garantia</strong>
                  <p>
                    Instale, rode os seus arquivos de verdade e feche um job inteiro, do jeito que
                    você faria num dia cheio. Se não fizer sentido para a sua gráfica, peça o
                    reembolso dentro dos 7 dias e devolvemos o valor.
                  </p>
                </div>
                <Spec
                  items={[
                    ["Sistema", "Windows 10 ou 11, 64 bits"],
                    ["Instalação", "Instalador assinado, sem configuração depois"],
                    ["Uso", "100% offline. Internet só para ativar, atualizar e receber suporte"],
                    ["Licença", "Vitalícia, para uso comercial na sua gráfica"],
                    ["Suporte", "Atendimento em português"],
                  ]}
                />
                <a className="pn-btn pn-btn-ghost" href={SUPPORT}>
                  Falar com o suporte antes
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------- faq */}
        <section id="faq" className="pn-section" style={{ paddingTop: 0 }}>
          <div className="pn-container">
            <div className="pn-head pn-reveal">
              <span className="pn-badge">Dúvidas</span>
              <h2>O que a gráfica pergunta antes de comprar.</h2>
              <p>
                Se ficar alguma pergunta de fora, o suporte responde em português antes de você
                pagar.
              </p>
            </div>
            <div className="pn-faq pn-reveal">
              {faqs.map((f, i) => (
                <details key={f.q} open={i === 0}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------- cta final */}
        <section className="pn-section" style={{ paddingTop: 0 }}>
          <div className="pn-container">
            <div className="pn-cta pn-reveal">
              <div>
                <h2>Feche a próxima chapa com o PrintNest.</h2>
                <p>
                  Pagamento único de R$ 397, licença vitalícia, instalador assinado para Windows 10 e
                  11. Instale, ative e monte um job real com os seus próprios arquivos. Nos primeiros
                  7 dias, o risco fica do nosso lado.
                </p>
              </div>
              <div className="pn-cta-actions">
                <a className="pn-btn pn-btn-light" href={PAY_LINK}>
                  <ShieldCheck aria-hidden="true" />
                  Comprar por R$ 397
                </a>
                <a className="pn-btn pn-btn-outline-light" href={SUPPORT}>
                  Tirar uma dúvida antes
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="pn-footer">
        <div className="pn-container">
          <div className="pn-footer-grid">
            <div className="pn-footer-about">
              <a className="pn-brand" href="#topo">
                <img src="/assets/printnest-symbol.png" alt="" />
                PrintNest
                <span>PRO</span>
              </a>
              <p>
                Software de desktop que prepara arquivo de produção gráfica: faca de corte, nesting,
                marcas de registro e exportação em PDF e DXF. Feito no Brasil, suporte em português.
              </p>
            </div>
            <div>
              <h4>Produto</h4>
              <nav>
                <a href="#recursos">Recursos</a>
                <a href="#fluxo">Como funciona</a>
                <a href="#compatibilidade">Compatibilidade</a>
              </nav>
            </div>
            <div>
              <h4>Comercial</h4>
              <nav>
                <a href="#preco">Preço e garantia</a>
                <a href="#faq">Dúvidas</a>
                <a href={SUPPORT}>Suporte</a>
              </nav>
            </div>
            <div>
              <h4>Legal</h4>
              <nav>
                <a href="#">Termos de uso</a>
                <a href="#">Privacidade</a>
                <a href="#">Reembolso em 7 dias</a>
              </nav>
            </div>
          </div>
          <div className="pn-footer-bottom">
            <span>© 2026 PrintNest Pro</span>
            <span>Windows 10 e 11 · 64 bits · uso offline</span>
          </div>
        </div>
      </footer>

      {/* seletor temporario de hero: apagar quando o modelo estiver escolhido */}
      <div className="pn-hero-switch">
        <b>Hero</b>
        {HERO_SKINS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={s.id === skin.id ? "is-on" : ""}
            onClick={() => setId(s.id)}
          >
            {s.nome}
          </button>
        ))}
      </div>

      {/* visualizador: abre a captura clicada e permite ver em tamanho real */}
      {item && (
        <div
          className="pn-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={item.alt || "Captura de tela do PrintNest"}
          onClick={close}
        >
          <button ref={closeRef} type="button" className="pn-lightbox-close" onClick={close}>
            <span aria-hidden="true">×</span>
            <span className="sr-only">Fechar</span>
          </button>

          <div
            className={`pn-lightbox-stage${full ? " is-full" : ""}`}
            onClick={(event) => event.stopPropagation()}
          >
            <img
              src={item.src}
              alt={item.alt}
              onClick={() => setFull((v) => !v)}
              draggable={false}
            />
          </div>

          <p className="pn-lightbox-caption">
            {item.caption}
            <span>
              {full
                ? "Tamanho real. Arraste para percorrer a tela, ou clique para encaixar de novo."
                : "Clique na imagem para ver em tamanho real. Esc fecha."}
            </span>
          </p>
        </div>
      )}
    </div>
  )
}
