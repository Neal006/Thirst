import { CopyCommand } from '../CopyCommand'

const STEPS = [
  {
    id: 'plan',
    name: 'Plan',
    line: 'best hours + power cap',
    icon: (
      <>
        <circle cx="24" cy="24" r="15" />
        <path className="ico-accent" d="M24 9 A15 15 0 0 1 37 16.5" />
        <path d="M24 24 L24 14 M24 24 L31 28" />
      </>
    ),
  },
  {
    id: 'run',
    name: 'Run',
    line: 'waits, caps, pauses',
    icon: (
      <>
        <rect x="8" y="13" width="32" height="22" rx="2" />
        <path d="M13 35 v4 M19 35 v4 M25 35 v4 M31 35 v4" />
        <path className="ico-accent ico-fill" d="M20 19 h3 v10 h-3z M26 19 h3 v10 h-3z" />
      </>
    ),
  },
  {
    id: 'receipt',
    name: 'Receipt',
    line: 'measured, signed',
    icon: (
      <>
        <path d="M13 7 h22 v33 l-3.7 -2.5 -3.6 2.5 -3.7 -2.5 -3.7 2.5 -3.6 -2.5 -3.7 2.5z" />
        <path d="M18 15 h12 M18 21 h12" />
        <path className="ico-accent" d="M18 28 h7" />
      </>
    ),
  },
  {
    id: 'rating',
    name: 'Rating',
    line: 'fair, by lab size',
    icon: (
      <>
        <path d="M6 40 h36" />
        <rect x="9" y="26" width="9" height="14" />
        <rect className="ico-accent ico-fill" x="19.5" y="16" width="9" height="24" />
        <rect x="30" y="30" width="9" height="10" />
      </>
    ),
  },
] as const

// A printed example. In <code> on purpose: it is a picture of a receipt, not a measurement.
const RECEIPT = `THIRST · WATER RECEIPT
job      j_tksft2nswiku
site     CSE GPU Lab · Chennai · D1
ran      11 Oct 02:00 → 08:40 IST
gpu      2 × RTX 4090 · cap 70%
────────────────────────────
energy   3.89 kWh    measured
water    16.5 L      modelled
co2      4.81 kg     modelled
vs now   −21% water · −21% co2
capture  86% of the possible saving
────────────────────────────
signed   hmac-sha256  ✓`

const RUN = 'thirst run --hours 6 --deadline "2026-10-11 09:00" --pausable -- python train.py'

export function LoopStrip() {
  return (
    <div className="loop">
      <div>
        <ol className="pipeline">
          {STEPS.map((s, i) => (
            <li key={s.id} className="pipe-step">
              <span className="pipe-num" aria-hidden="true">
                0{i + 1}
              </span>
              <svg className="pipe-ico" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
                {s.icon}
              </svg>
              <b>{s.name}</b>
              <span>{s.line}</span>
            </li>
          ))}
        </ol>
        <div className="loop-cmd">
          <span className="loop-cmd-label">One command does all four</span>
          <CopyCommand command={RUN} />
        </div>
      </div>
      <div className="receipt-paper" role="img" aria-label="A sample water receipt: energy measured from the GPU, water and CO2 modelled from it, compared with starting right away">
        <span className="receipt-stamp" aria-hidden="true">
          Sample
        </span>
        <pre aria-hidden="true">
          <code>{RECEIPT}</code>
        </pre>
      </div>
    </div>
  )
}
