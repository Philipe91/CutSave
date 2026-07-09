import { useCallback, useEffect, useRef } from "react"
import type { RefObject } from "react"

/**
 * Renderizador de frames em canvas fullscreen:
 * - redimensiona com devicePixelRatio (cap em 2 para poupar memória)
 * - desenha em "contain" (nunca corta conteúdo importante)
 * - preenche as bordas com a cor de fundo amostrada do próprio frame,
 *   para o canvas se fundir com a página sem emendas visíveis
 */
export function useCanvasRenderer(
  canvasRef: RefObject<HTMLCanvasElement | null>,
  images: (HTMLImageElement | null)[]
) {
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null)
  const bgColorRef = useRef<string>("#050d1c")
  const lastDrawnRef = useRef(-1)

  /* Amostra a cor do canto do primeiro frame disponível (fundo da cena) */
  const sampleBackground = useCallback(() => {
    const img = images.find(Boolean)
    if (!img) return bgColorRef.current
    try {
      const probe = document.createElement("canvas")
      probe.width = probe.height = 4
      const pctx = probe.getContext("2d", { willReadFrequently: true })
      if (!pctx) return bgColorRef.current
      pctx.drawImage(img, 0, 0, 12, 12, 0, 0, 4, 4)
      const [r, g, b] = pctx.getImageData(1, 1, 1, 1).data
      bgColorRef.current = `rgb(${r}, ${g}, ${b})`
    } catch {
      /* mantém fallback */
    }
    return bgColorRef.current
  }, [images])

  const resize = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const { clientWidth, clientHeight } = canvas
    const w = Math.round(clientWidth * dpr)
    const h = Math.round(clientHeight * dpr)
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      lastDrawnRef.current = -1 // força redesenho após resize
    }
    if (!ctxRef.current) {
      ctxRef.current = canvas.getContext("2d")
      if (ctxRef.current) {
        ctxRef.current.imageSmoothingEnabled = true
        ctxRef.current.imageSmoothingQuality = "high"
      }
    }
  }, [canvasRef])

  const drawFrame = useCallback(
    (index: number, force = false) => {
      const canvas = canvasRef.current
      const ctx = ctxRef.current
      const img = images[index]
      if (!canvas || !ctx || !img) return
      if (!force && lastDrawnRef.current === index) return
      lastDrawnRef.current = index

      const cw = canvas.width
      const ch = canvas.height

      ctx.fillStyle = bgColorRef.current
      ctx.fillRect(0, 0, cw, ch)

      const scale = Math.min(cw / img.naturalWidth, ch / img.naturalHeight)
      const dw = img.naturalWidth * scale
      const dh = img.naturalHeight * scale
      ctx.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh)
    },
    [canvasRef, images]
  )

  useEffect(() => {
    resize()
    const onResize = () => {
      resize()
      if (lastDrawnRef.current !== -1) {
        const last = lastDrawnRef.current
        lastDrawnRef.current = -1
        drawFrame(last, true)
      }
    }
    window.addEventListener("resize", onResize, { passive: true })
    return () => window.removeEventListener("resize", onResize)
  }, [resize, drawFrame])

  return { drawFrame, resize, sampleBackground, bgColorRef }
}
