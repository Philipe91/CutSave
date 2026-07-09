import { useEffect, useRef, useState } from "react"

/**
 * Variantes do hero scrollytelling. Cada vídeo processado por
 * `scripts/extract-hero-frames.py` vira uma pasta em
 * `src/assets/hero-variants/<nome>/{hd,sd}/` e é detectado aqui
 * automaticamente em build time — nada de hardcode.
 *
 * A variante ativa vem de `?hero=<nome>` na URL (ou da última escolha salva),
 * e o visitante baixa apenas a camada (HD/SD) adequada à tela dele.
 */
const hdModules = import.meta.glob<{ default: string }>(
  "../assets/hero-variants/*/hd/*.jpg",
  { eager: true }
)
const sdModules = import.meta.glob<{ default: string }>(
  "../assets/hero-variants/*/sd/*.jpg",
  { eager: true }
)

function groupByVariant(mods: Record<string, { default: string }>) {
  const map: Record<string, string[]> = {}
  for (const key of Object.keys(mods).sort()) {
    const match = key.match(/hero-variants\/([^/]+)\//)
    if (!match) continue
    ;(map[match[1]] ??= []).push(mods[key].default)
  }
  return map
}

const HD_BY_VARIANT = groupByVariant(hdModules)
const SD_BY_VARIANT = groupByVariant(sdModules)

export const VARIANTS: string[] = Object.keys(HD_BY_VARIANT).sort()

const STORAGE_KEY = "printnest-hero-variant"

function pickVariant(): string {
  if (typeof window === "undefined") return VARIANTS[0]
  const fromUrl = new URLSearchParams(window.location.search).get("hero")
  if (fromUrl && VARIANTS.includes(fromUrl)) return fromUrl
  const saved = window.localStorage.getItem(STORAGE_KEY)
  if (saved && VARIANTS.includes(saved)) return saved
  return VARIANTS[0]
}

export const ACTIVE_VARIANT = pickVariant()

/* ---------- layout do hero: scrollytelling ou vídeo ao lado ---------- */

export type HeroLayout = "scroll" | "video"

const LAYOUT_KEY = "printnest-hero-layout"

function pickLayout(): HeroLayout {
  if (typeof window === "undefined") return "scroll"
  const fromUrl = new URLSearchParams(window.location.search).get("layout")
  if (fromUrl === "video" || fromUrl === "scroll") return fromUrl
  const saved = window.localStorage.getItem(LAYOUT_KEY)
  if (saved === "video" || saved === "scroll") return saved
  return "scroll"
}

export const ACTIVE_LAYOUT: HeroLayout = pickLayout()

/** Troca a variante ativa (layout scroll) e recarrega para reiniciar o preload */
export function switchVariant(name: string) {
  if (!VARIANTS.includes(name)) return
  window.localStorage.setItem(STORAGE_KEY, name)
  window.localStorage.setItem(LAYOUT_KEY, "scroll")
  const url = new URL(window.location.href)
  url.searchParams.set("hero", name)
  url.searchParams.set("layout", "scroll")
  window.location.href = url.toString()
}

/** Troca o layout do hero (scroll × vídeo ao lado) e recarrega */
export function switchLayout(layout: HeroLayout) {
  window.localStorage.setItem(LAYOUT_KEY, layout)
  const url = new URL(window.location.href)
  url.searchParams.set("layout", layout)
  window.location.href = url.toString()
}

/* HD (1920 de largura) para telas grandes/retina; SD para o resto */
const wantsHd =
  typeof window !== "undefined" &&
  window.innerWidth * (window.devicePixelRatio || 1) > 1400

export const FRAME_URLS: string[] =
  (wantsHd ? HD_BY_VARIANT[ACTIVE_VARIANT] : SD_BY_VARIANT[ACTIVE_VARIANT]) ??
  HD_BY_VARIANT[ACTIVE_VARIANT] ??
  []

export const FRAME_COUNT = FRAME_URLS.length

/** Sempre a melhor qualidade — para <img> estáticos fora do hero */
export const FRAME_URLS_HD: string[] = HD_BY_VARIANT[ACTIVE_VARIANT] ?? FRAME_URLS

export type SequenceState = {
  /** imagens decodificadas, indexadas por frame */
  images: (HTMLImageElement | null)[]
  /** 0..1 — fração de frames carregados */
  progress: number
  /** true quando todos os frames estão prontos para desenhar */
  ready: boolean
}

/**
 * Pré-carrega e decodifica todos os frames da sequência, reportando progresso.
 * As imagens são mantidas em memória para desenho instantâneo no canvas.
 */
export function useImageSequence(): SequenceState {
  const imagesRef = useRef<(HTMLImageElement | null)[]>(FRAME_URLS.map(() => null))
  const [progress, setProgress] = useState(0)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    let loaded = 0

    const tasks = FRAME_URLS.map((url, i) => {
      const img = new Image()
      img.decoding = "async"
      img.src = url
      return img
        .decode()
        .catch(() => {
          /* decode() pode falhar em navegadores antigos; onload cobre o resto */
          return new Promise<void>((resolve) => {
            if (img.complete) return resolve()
            img.onload = () => resolve()
            img.onerror = () => resolve()
          })
        })
        .then(() => {
          if (cancelled) return
          imagesRef.current[i] = img
          loaded += 1
          setProgress(loaded / FRAME_URLS.length)
        })
    })

    Promise.all(tasks).then(() => {
      if (!cancelled) setReady(true)
    })

    return () => {
      cancelled = true
    }
  }, [])

  return { images: imagesRef.current, progress, ready }
}
