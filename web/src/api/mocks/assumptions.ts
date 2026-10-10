// A small typed copy of GET /assumptions for mock mode and tests. Values come from
// src/engine/data (a subset); the real page reads the full table from the API.

import type { AssumptionRow, AssumptionsResponse, CityRow, GpuRow, SourceRow } from '../types'

function factor(
  id: string,
  group: string,
  label: string,
  value: number,
  unit: string,
  status: AssumptionRow['status'],
  spread = 0,
  source = 'trd.md 5',
): AssumptionRow {
  return {
    id,
    group,
    label,
    value,
    low: value * (1 - spread),
    high: value * (1 + spread),
    unit,
    status,
    source,
    source_url: '',
    notes: status === 'placeholder' ? 'Replace with a measured or datasheet value.' : '',
  }
}

const FACTORS: AssumptionRow[] = [
  factor('cop_rated_room_ac', 'cooling', 'Rated COP of a room AC', 3, 'kW heat per kW', 'placeholder', 0.15),
  factor('wue_a', 'cooling', 'Water used on site per kWh at 0 degC wet-bulb', 0.2, 'L/kWh', 'placeholder', 0.3),
  factor('cea_grid_ef', 'grid_carbon', 'National average grid emission factor', 0.727, 'kg/kWh', 'sourced', 0, 'CEA'),
  factor('ef_coal', 'grid_carbon', 'Coal emission factor', 0.95, 'kg/kWh', 'calibrated', 0.15, 'CEA'),
  factor('wf_coal', 'grid_water', 'Water consumed per kWh of coal power', 3.25, 'L/kWh', 'sourced', 0.2, 'MoEFCC'),
  factor('stress_high', 'stress', 'Water stress weight, high', 2, 'multiplier', 'design_choice'),
  factor('tau_70', 'gpu', 'Run time at 70% power cap', 0.9, 'ratio', 'placeholder', 0.1),
  factor('eps_70', 'gpu', 'Energy per unit of work at 70% power cap', 0.8, 'ratio', 'placeholder', 0.1),
  factor('badge_gold', 'score', 'Score needed for a gold badge', 75, 'points', 'design_choice'),
  factor('person_day_l', 'people', 'Water one person uses in a day', 135, 'L', 'sourced', 0, 'CPHEEO'),
]

const GPUS: GpuRow[] = [
  { id: 'RTX-4090', label: 'NVIDIA GeForce RTX 4090', p_max_w: 450, p_idle_w: 45, sweep_status: 'placeholder' },
  { id: 'RTX-3090', label: 'NVIDIA GeForce RTX 3090', p_max_w: 350, p_idle_w: 35, sweep_status: 'placeholder' },
  { id: 'A100-PCIE-40GB', label: 'NVIDIA A100 PCIe 40GB', p_max_w: 250, p_idle_w: 25, sweep_status: 'placeholder' },
  { id: 'H100-SXM', label: 'NVIDIA H100 SXM', p_max_w: 700, p_idle_w: 70, sweep_status: 'placeholder' },
]

const CITIES: CityRow[] = [
  { id: 'Chennai', stress_category: 'extremely_high', stress_weight: 2.5, status: 'placeholder' },
  { id: 'Bengaluru', stress_category: 'high', stress_weight: 2, status: 'placeholder' },
  { id: 'Hyderabad', stress_category: 'high', stress_weight: 2, status: 'placeholder' },
  { id: 'Mumbai', stress_category: 'high', stress_weight: 2, status: 'placeholder' },
  { id: 'Delhi', stress_category: 'extremely_high', stress_weight: 2.5, status: 'placeholder' },
  { id: 'Pune', stress_category: 'medium_high', stress_weight: 1.5, status: 'placeholder' },
]

const SOURCES: SourceRow[] = [
  {
    name: 'Open-Meteo',
    url: 'https://open-meteo.com/',
    licence: 'CC BY 4.0',
    used_for: 'hourly temperature, humidity and sunshine forecast',
  },
  {
    name: 'WRI Aqueduct',
    url: 'https://www.wri.org/aqueduct',
    licence: 'CC BY 4.0',
    used_for: 'baseline water stress category of each city',
  },
]

export const MOCK_ASSUMPTIONS: AssumptionsResponse = {
  version: 'mock-1',
  factors: FACTORS,
  gpus: GPUS,
  cities: CITIES,
  stress_weights: {
    low: 1,
    low_medium: 1.25,
    medium_high: 1.5,
    high: 2,
    extremely_high: 2.5,
  },
  sources: SOURCES,
}
