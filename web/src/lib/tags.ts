// Tag -> label, style and anchor (plan 6.4.b). Every number is labelled measured or modelled
// (PRD G5); the chip links to the explanation on the Assumptions page.

import type { FactorStatus } from '../api/types'

export interface TagInfo {
  label: string
  className: string
  anchor: string
  help: string
}

const HELP: Record<string, string> = {
  measured: 'Read from the hardware on your machine.',
  modelled: 'Calculated from a model, not measured. Read how on the Assumptions page.',
  placeholder: 'A stand-in value until we measure the real one. Treat it as a rough guess.',
  sourced: 'Taken from a published source that we cite.',
  calibrated: 'Adjusted so that the model matches a published yearly figure.',
  unverified: 'Reported by the tool but not checked against the hardware.',
  design_choice: 'A choice we made on purpose, not a measurement.',
}

const UNKNOWN: TagInfo = {
  label: 'unknown',
  className: 'tag tag-unknown',
  anchor: 'legend-heading',
  help: 'The server did not say how sure this number is. Explained on the Assumptions page.',
}

export function tagInfo(tag: FactorStatus): TagInfo {
  // The type says string, but a reply can still hold anything: never print "undefined".
  if (typeof tag !== 'string' || tag.trim() === '') return UNKNOWN
  const name = tag
  return {
    label: name.replace(/_/g, ' '),
    className: `tag tag-${name.replace(/_/g, '-')}`,
    anchor: `status-${name}`,
    help: HELP[name] ?? 'Explained on the Assumptions page.',
  }
}
