import {
  ACTIVE_LAYOUT,
  ACTIVE_VARIANT,
  VARIANTS,
  switchLayout,
  switchVariant,
} from "@/hooks/useImageSequence"

/**
 * Seletor flutuante para comparar as versões do hero (variantes de vídeo do
 * scrollytelling + layout "vídeo ao lado"). Remover quando a vencedora for
 * escolhida.
 */
export function HeroSwitcher() {
  const options = VARIANTS.length + 1
  if (options < 2) return null

  return (
    <div className="aph-variant-switcher" aria-label="Comparar versões do hero">
      <span>Hero:</span>
      {VARIANTS.map((v) => (
        <button
          key={v}
          className={
            ACTIVE_LAYOUT === "scroll" && v === ACTIVE_VARIANT ? "is-active" : ""
          }
          onClick={() => switchVariant(v)}
        >
          {v.replace(/^v\d+-/, "")}
        </button>
      ))}
      <button
        className={ACTIVE_LAYOUT === "video" ? "is-active" : ""}
        onClick={() => switchLayout("video")}
      >
        vídeo ao lado
      </button>
    </div>
  )
}
