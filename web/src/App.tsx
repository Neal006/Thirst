import { useMemo } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import type { ApiClient } from './api/client'
import { ApiContext } from './api/context'
import { createDefaultClient } from './api/defaultClient'
import { appRoutes } from './routes'

type AppRouter = ReturnType<typeof createBrowserRouter>

interface AppProps {
  /** Replaced in tests; the app builds its own from VITE_API_URL / VITE_USE_MOCKS. */
  client?: ApiClient
  router?: AppRouter
}

function buildClient(): { client: ApiClient } | { problem: string } {
  try {
    return { client: createDefaultClient(import.meta.env) }
  } catch (error) {
    return { problem: error instanceof Error ? error.message : 'The app is not set up.' }
  }
}

function App({ client, router }: AppProps) {
  const setup = useMemo(() => (client ? { client } : buildClient()), [client])
  const activeRouter = useMemo(() => router ?? createBrowserRouter(appRoutes), [router])

  if ('problem' in setup) {
    return (
      <main className="app-main">
        <h1>Thirst can't start</h1>
        <p>{setup.problem}</p>
      </main>
    )
  }
  return (
    <ApiContext.Provider value={setup.client}>
      <RouterProvider router={activeRouter} />
    </ApiContext.Provider>
  )
}

export default App
