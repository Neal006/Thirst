import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { FactorStatus } from '../api/types'
import { CopyCommand } from '../components/CopyCommand'
import { Beakers } from '../components/landing/Beakers'
import { BoardPreview } from '../components/landing/BoardPreview'
import { Hero } from '../components/landing/Hero'
import { LoopStrip } from '../components/landing/LoopStrip'
import { PowerCap } from '../components/landing/PowerCap'
import { TagChip } from '../components/TagChip'
import { useAssumptions } from '../hooks/useAssumptions'
import { useCityForecast } from '../hooks/useCityForecast'
import { usePageTitle } from '../hooks/usePageTitle'
import { useReveal } from '../hooks/useReveal'
import { FALLBACK_CITIES } from '../lib/landing'
import { tagInfo } from '../lib/tags'
import './landing.css'

const LEGEND: readonly FactorStatus[] = ['measured', 'modelled', 'sourced', 'calibrated', 'placeholder']

const INSTALL = 'pip install "git+https://github.com/Neal006/Thirst#subdirectory=cli"'
const REGISTER = 'thirst register --name "CSE GPU Lab" --city Chennai --cooling room_ac --gpus 4'

export function LandingPage() {
  usePageTitle('Every GPU hour drinks water twice')
  const root = useRef<HTMLDivElement>(null)
  useReveal(root)
  const { state } = useAssumptions()
  const ready = state.status === 'ready' ? state.data : null
  const cities = ready?.cities.length ? ready.cities.map((c) => c.id) : [...FALLBACK_CITIES]
  const [city, setCity] = useState<string>('Chennai')
  const forecast = useCityForecast(city)

  return (
    <div className="landing" ref={root}>
      <Hero
        cities={cities}
        cityRows={ready?.cities}
        city={city}
        onCity={setCity}
        forecast={forecast.state}
        reload={forecast.reload}
      />

      <section className="section reveal" aria-labelledby="twice-title">
        <div className="section-head">
          <p className="eyebrow">Same job · two start times</p>
          <h2 id="twice-title" className="section-title">
            Where the water goes
          </h2>
        </div>
        <Beakers city={city} />
      </section>

      <section className="section reveal" aria-labelledby="cap-title">
        <div className="section-head">
          <p className="eyebrow">The speed knob</p>
          <h2 id="cap-title" className="section-title">
            A slower GPU drinks less
          </h2>
        </div>
        <PowerCap factors={ready?.factors} />
      </section>

      <section id="how" className="section reveal" aria-labelledby="loop-title">
        <div className="section-head">
          <p className="eyebrow">How it works</p>
          <h2 id="loop-title" className="section-title">
            Plan · Run · Receipt · Rating
          </h2>
        </div>
        <LoopStrip />
      </section>

      <BoardPreview />

      <section className="section reveal" aria-labelledby="honesty-title">
        <div className="honesty">
          <h2 id="honesty-title" className="honesty-title">
            Every number wears a label
          </h2>
          <ul className="legend">
            {LEGEND.map((tag) => (
              <li key={tag} title={tagInfo(tag).help}>
                <TagChip tag={tag} />
                <span>{tagInfo(tag).help}</span>
              </li>
            ))}
          </ul>
          <Link className="btn" to="/assumptions">
            All assumptions <span className="btn-arrow" aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

      <section className="section start reveal" aria-labelledby="start-title">
        <h2 id="start-title" className="final-line">
          Tonight's run can drink <em>less</em>.
        </h2>
        <div className="start-grid">
          <ol className="start-steps">
            <li>
              <CopyCommand command={INSTALL} />
            </li>
            <li>
              <CopyCommand command={REGISTER} />
            </li>
          </ol>
          <Link className="btn btn-primary btn-lg" to={`/plan?city=${encodeURIComponent(city)}`}>
            Plan it now <span className="btn-arrow" aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </div>
  )
}
