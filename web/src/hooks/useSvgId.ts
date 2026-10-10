import { useId } from 'react'

/** A unique id safe inside SVG `url(#...)` references (React's ids contain colons or guillemets). */
export function useSvgId(prefix: string): string {
  return `${prefix}-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
}
