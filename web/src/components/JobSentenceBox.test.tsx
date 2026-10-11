import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import { createDefaultClient } from '../api/defaultClient'
import { ApiContext } from '../api/context'
declare const process: any
import { JobSentenceBox } from './JobSentenceBox'

/** Ensure the mock fetch is used */
process.env.VITE_USE_MOCKS = 'true'

describe('JobSentenceBox', () => {
  it('submits text and shows mock explanation', async () => {
    const client = createDefaultClient({ VITE_USE_MOCKS: 'true' })
    render(
      <MemoryRouter>
        <ApiContext.Provider value={client}>
          <JobSentenceBox />
        </ApiContext.Provider>
      </MemoryRouter>,
    )
    const textarea = screen.getByLabelText('Job description') as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: 'sample job description' } })
    const button = screen.getByRole('button', { name: /Explain/i })
    fireEvent.click(button)
    await waitFor(() => expect(screen.getByText(/Explanation for:/)).toBeInTheDocument())
    expect(screen.getByText(/template/)).toBeInTheDocument()
  })
})
