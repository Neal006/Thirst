import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('shows the product name and the build status', () => {
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Thirst' })).toBeInTheDocument()
    expect(screen.getByText(/plan, run, receipt, rating/i)).toBeInTheDocument()
  })
})
