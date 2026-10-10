import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './theme.css'
import './pages.css'
import App from './App.tsx'

const root = document.getElementById('root')
if (!root) throw new Error('The page has no #root element.')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
