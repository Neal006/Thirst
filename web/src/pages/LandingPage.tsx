import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CopyCommand } from '../components/CopyCommand'
import { Beakers } from '../components/landing/Beakers'
import { BoardPreview } from '../components/landing/BoardPreview'
import { Hero } from '../components/landing/Hero'
import { LoopStrip } from '../components/landing/LoopStrip'
import { PowerCap } from '../components/landing/PowerCap'
import { useAssumptions } from '../hooks/useAssumptions'
import { useCityForecast } from '../hooks/useCityForecast'
import { usePageTitle } from '../hooks/usePageTitle'
import { useReveal } from '../hooks/useReveal'
import { FALLBACK_CITIES } from '../lib/landing'
import './landing.css'

const INSTALL = 'pip install thirst'
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
          <h2 id="twice-title" className="section-title">
            Where the water goes
          </h2>
        </div>
        <Beakers city={city} />
      </section>

      <section className="section reveal" aria-labelledby="cap-title">
        <div className="section-head">
          <h2 id="cap-title" className="section-title">
            A slower GPU drinks less
          </h2>
        </div>
        <PowerCap factors={ready?.factors} />
      </section>

      <section id="how" className="section reveal" aria-labelledby="loop-title">
        <div className="section-head">
          <h2 id="loop-title" className="section-title">
            How it works
          </h2>
        </div>
        <LoopStrip />
      </section>

      <BoardPreview />

      <section className="section start reveal" aria-labelledby="start-title">
        <h2 id="start-title" className="final-line">
          Start in two steps
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
            Open the planner <span className="btn-arrow" aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </div>
  )
}
