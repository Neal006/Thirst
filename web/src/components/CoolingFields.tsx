import { COOLING_OPTIONS, type CoolingId } from '../lib/jobForm'
import { FormField } from './FormField'

interface CoolingFieldsProps {
  cooling: CoolingId
  pue: string
  pueError?: string
  onCooling: (cooling: CoolingId) => void
  onPue: (pue: string) => void
}

const isCooling = (value: string): value is CoolingId =>
  COOLING_OPTIONS.some((option) => option.id === value)

/** The cooling type, and the PUE only for a cooling tower. */
export function CoolingFields({ cooling, pue, pueError, onCooling, onPue }: CoolingFieldsProps) {
  return (
    <>
      <FormField id="cooling" label="Cooling">
        {(c) => (
          <select
            {...c}
            value={cooling}
            onChange={(e) => isCooling(e.target.value) && onCooling(e.target.value)}
          >
            {COOLING_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </FormField>
      {cooling === 'evaporative' ? (
        <FormField
          id="pue"
          label="PUE (power usage effectiveness)"
          help="Total site power divided by IT power. 1.4 is a common value."
          error={pueError}
        >
          {(c) => (
            <input
              {...c}
              type="number"
              inputMode="decimal"
              min={1}
              max={3}
              step={0.1}
              value={pue}
              onChange={(e) => onPue(e.target.value)}
            />
          )}
        </FormField>
      ) : null}
    </>
  )
}
