import type { AssumptionsResponse, FactorStatus } from '../api/types'
import { plainNumber, safeUrl } from '../lib/assumptionsView'
import { tagInfo } from '../lib/tags'
import { TagChip } from './TagChip'

const LEGEND: FactorStatus[] = [
  'measured',
  'modelled',
  'placeholder',
  'sourced',
  'calibrated',
  'design_choice',
  'unverified',
]

/** What each label means. The ids are where the chips on every other page link to. */
export function StatusLegend() {
  return (
    <section className="card" aria-labelledby="legend-heading">
      <h2 id="legend-heading">What the labels mean</h2>
      <ul className="stat-list">
        {LEGEND.map((tag) => {
          const info = tagInfo(tag)
          return (
            <li key={tag} id={info.anchor}>
              <TagChip tag={tag} /> {info.help}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function GpuTable({ gpus }: { gpus: AssumptionsResponse['gpus'] }) {
  return (
    <section className="card" aria-labelledby="gpus-heading">
      <h2 id="gpus-heading">GPUs</h2>
      <table className="data-table cards-on-phone">
        <thead>
          <tr>
            <th scope="col">GPU</th>
            <th scope="col">Maximum power</th>
            <th scope="col">Power-cap sweep</th>
          </tr>
        </thead>
        <tbody>
          {gpus.map((g) => (
            <tr key={g.id}>
              <td data-label="GPU">{g.label}</td>
              <td data-label="Maximum power">{`${plainNumber(g.p_max_w)} W`}</td>
              <td data-label="Power-cap sweep"><TagChip tag={g.sweep_status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function CityTable({ cities }: { cities: AssumptionsResponse['cities'] }) {
  return (
    <section className="card" aria-labelledby="cities-heading">
      <h2 id="cities-heading">Cities</h2>
      <table className="data-table cards-on-phone">
        <thead>
          <tr>
            <th scope="col">City</th>
            <th scope="col">Water stress</th>
            <th scope="col">Weight</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {cities.map((c) => (
            <tr key={c.id}>
              <td data-label="City">{c.id}</td>
              <td data-label="Water stress">{c.stress_category.replace(/_/g, ' ')}</td>
              <td data-label="Weight">{`${plainNumber(c.stress_weight)}x`}</td>
              <td data-label="Status"><TagChip tag={c.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function SourceList({ sources }: { sources: AssumptionsResponse['sources'] }) {
  return (
    <section className="card" aria-labelledby="sources-heading">
      <h2 id="sources-heading">Sources</h2>
      <ul className="stat-list">
        {sources.map((s) => {
          const href = safeUrl(s.url)
          return (
            <li key={s.name}>
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {s.name}
                </a>
              ) : (
                <strong>{s.name}</strong>
              )}{' '}
              <span className="stat-label">
                {s.used_for}. Licence: {s.licence}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
