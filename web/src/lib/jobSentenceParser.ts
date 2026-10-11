// src/lib/jobSentenceParser.ts
// Simple deterministic parser copying the Python logic for the front‑end.
// Returns extracted values and an ordered list of found keys.

export interface ParsedSentence {
  work_hours: number | null
  gpu_count: number | null
  city: string | null
  workload: string | null
  found: string[]
}

const CITIES = ['Chennai', 'Bengaluru', 'Hyderabad', 'Mumbai', 'Delhi', 'Pune']
const WORKLOADS = ['lora', 'training', 'inference', 'finetune', 'fine‑tune']

export function parseJobSentence(text: string): ParsedSentence {
  const result: ParsedSentence = {
    work_hours: null,
    gpu_count: null,
    city: null,
    workload: null,
    found: [],
  }

  // gpu count – number before an 'x'
  const gMatch = text.match(/(\d+)\s*[xX]\s*\d+/)
  if (gMatch) {
    result.gpu_count = parseInt(gMatch[1], 10)
    result.found.push('gpu_count')
  }

  // work hours – number followed by hour(s) or hr(s)
  const hMatch = text.match(/(\d+(?:\.\d+)?)\s*(hours?|hrs?)/i)
  if (hMatch) {
    result.work_hours = parseFloat(hMatch[1])
    result.found.push('work_hours')
  }

  // city – first matching known city name (case‑insensitive)
  for (const city of CITIES) {
    const re = new RegExp(`\\b${city}\\b`, 'i')
    if (re.test(text)) {
      result.city = city
      result.found.push('city')
      break
    }
  }

  // workload – keyword detection
  for (const kw of WORKLOADS) {
    const re = new RegExp(`\\b${kw}\\b`, 'i')
    if (re.test(text)) {
      result.workload = kw
      result.found.push('workload')
      break
    }
  }

  // deduplicate while preserving order
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const key of result.found) {
    if (!seen.has(key)) {
      seen.add(key)
      ordered.push(key)
    }
  }
  result.found = ordered
  return result
}
