export const DIVISIONS = [
  { id: 'D1', label: 'Small labs (up to 16 GPUs)' },
  { id: 'D2', label: 'Clusters (17 to 256)' },
  { id: 'D3', label: 'Facilities (257 to 4,096)' },
  { id: 'D4', label: 'Hyperscale (above 4,096)' },
] as const

export const DEFAULT_DIVISION = 'D1'

/** The division to show for a query value: unknown or missing means D1. */
export function parseDivision(value: string | null): string {
  return DIVISIONS.find((d) => d.id === value)?.id ?? DEFAULT_DIVISION
}

export function divisionLabel(id: string): string {
  return DIVISIONS.find((d) => d.id === id)?.label ?? id
}

const COOLING_NAMES: Record<string, string> = {
  room_ac: 'Room AC',
  air_chiller: 'Air-cooled chiller',
  evaporative: 'Cooling tower',
}

export function coolingLabel(id: string): string {
  return COOLING_NAMES[id] ?? id
}
