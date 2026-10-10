import { alphaText, alphaWords, snapAlpha } from '../lib/planView'

interface AlphaSliderProps {
  /** Weight on water, 0 to 1 on a 0.1 grid. */
  value: number
  onChange: (alpha: number) => void
}

/** F3: trade water against carbon. It only picks another Pareto entry; it makes no request. */
export function AlphaSlider({ value, onChange }: AlphaSliderProps) {
  const alpha = snapAlpha(value)
  return (
    <div className="card">
      <label htmlFor="alpha-slider">
        <strong>Save carbon ←→ Save water</strong>
      </label>
      <div className="slider-row">
        <input
          id="alpha-slider"
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={alpha}
          aria-valuetext={alphaText(alpha)}
          onChange={(event) => onChange(snapAlpha(event.currentTarget.valueAsNumber))}
        />
        <output htmlFor="alpha-slider">{alphaWords(alpha)}</output>
      </div>
    </div>
  )
}
