// Plain-words names for the codes a receipt carries.

import { defaultDeadline } from './deadline'

const METHODS: Record<string, string> = {
  nvml_energy: 'NVML energy counter (read from the GPU)',
  nvml_power_integration: 'NVML power readings added up over time',
  modelled: 'Modelled from the GPU type, no hardware reading',
  unverified: 'Unverified',
}

const CAP_METHODS: Record<string, string> = {
  nvml: 'NVML',
  nvidia_smi: 'nvidia-smi',
  clock_lock: 'clock lock',
  none: 'none',
}

export function methodLabel(method: string): string {
  return METHODS[method] ?? 'Not stated'
}

export function capMethodLabel(method: string): string {
  return CAP_METHODS[method] ?? 'not stated'
}

/** The tag for the energy a receipt reports: measured only when read from the hardware. */
export function isMeasuredMethod(method: string | undefined): boolean {
  return method === 'nvml_energy' || method === 'nvml_power_integration'
}

/** What a first run could look like: a deadline of tomorrow 09:00 India time, never a fixed date. */
export function exampleCommand(nowMs: number): string {
  const deadline = defaultDeadline(nowMs).replace('T', ' ')
  return `thirst run --hours 6 --deadline "${deadline}" --pausable -- python train.py`
}
