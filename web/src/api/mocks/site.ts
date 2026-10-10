// Builds a typed GET /sites/{id} reply for mock mode from a leaderboard row (or a new empty site).

import type { LeaderboardRow, SiteResponse } from '../types'

export const EMPTY_SITE_ID = 's_emptyaaaaa'

const DEMO_JOB_IDS = ['j_abcdefghijkl', 'j_abcdefghijkm', 'j_abcdefghijkn']
const DEMO_END = Date.parse('2026-10-09T08:00:00+05:30')
const DAY_MS = 86_400_000

export function emptySite(): SiteResponse {
  return {
    site: {
      site_id: EMPTY_SITE_ID,
      name: 'New Lab, Pune',
      org: null,
      city: 'Pune',
      cooling: 'room_ac',
      division: 'D1',
      simulated: false,
      public: true,
    },
    score: {
      value: null,
      provisional: true,
      badge: null,
      A: 0,
      B: 'not_rated',
      C: 5,
      C_parts: { measured_share: 0, coverage: 0, public: 5 },
      flex_share: 0,
      reason: 'needs_flexible_receipt',
    },
    monthly_absolute: null,
    recent_receipts: [],
  }
}

export function siteFromRow(row: LeaderboardRow): SiteResponse {
  const measuredShare = row.simulated ? 0 : 10
  return {
    site: {
      site_id: row.site_id,
      name: row.name,
      org: null,
      city: row.name.includes('Bengaluru') ? 'Bengaluru' : 'Chennai',
      cooling: 'room_ac',
      division: row.division,
      simulated: row.simulated,
      public: true,
    },
    score: {
      value: row.score,
      provisional: true,
      badge: row.badge,
      A: row.A,
      B: 'not_rated',
      C: row.C,
      C_parts: { measured_share: measuredShare, coverage: 5, public: 5 },
      flex_share: row.flex_share,
      reason: row.score === null ? 'needs_flexible_receipt' : null,
    },
    monthly_absolute: row.monthly_absolute,
    recent_receipts: DEMO_JOB_IDS.slice(0, Math.min(row.receipts, DEMO_JOB_IDS.length)).map(
      (job_id, i) => ({
        job_id,
        end_ts: new Date(DEMO_END - i * DAY_MS).toISOString(),
        kwh: 4.5 - i * 0.5,
        capture: i === 2 ? null : 0.86 - i * 0.1,
        no_room: i === 2,
        method: row.simulated ? 'modelled' : 'nvml_energy',
      }),
    ),
  }
}
