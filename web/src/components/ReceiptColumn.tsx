import type { FactorStatus, FootprintTotals, ReceiptResponse } from '../api/types'
import { Amount } from './Amount'

interface ReceiptColumnProps {
  id: string
  title: string
  totals: FootprintTotals
  /** Tag for the GPU energy line: measured only for what the person actually ran. */
  energyTag: FactorStatus
  tags: ReceiptResponse['tags']
}

/** One way of running the job (right away, best plan, what you did) with its footprint. */
export function ReceiptColumn({ id, title, totals, energyTag, tags }: ReceiptColumnProps) {
  const rows: { label: string; value: number; unit: string; tag: FactorStatus }[] = [
    { label: 'Energy at the GPU', value: totals.E_gpu_kwh, unit: 'kWh', tag: energyTag },
    { label: 'Energy at the building', value: totals.E_fac_kwh, unit: 'kWh', tag: 'modelled' },
    { label: 'Water used', value: totals.litres, unit: 'L', tag: tags.water },
    { label: 'Stress-weighted water', value: totals.W_l, unit: 'L', tag: tags.water },
    { label: 'CO₂', value: totals.C_kg, unit: 'kg', tag: tags.co2 },
    { label: 'City water', value: totals.person_days, unit: 'person-days', tag: tags.water },
  ]
  return (
    <section className="card" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <ul className="stat-list">
        {rows.map((row) => (
          <li key={row.label}>
            <span className="stat-label">{row.label}</span>
            <Amount value={row.value} unit={row.unit} tag={row.tag} />
          </li>
        ))}
      </ul>
    </section>
  )
}
