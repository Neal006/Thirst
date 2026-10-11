import { useParams } from 'react-router-dom'
import { ReceiptView } from '../components/ReceiptView'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { usePageTitle } from '../hooks/usePageTitle'
import { useReceipt } from '../hooks/useReceipt'
import { useSite } from '../hooks/useSite'

export function ReceiptPage() {
  const { siteId = '', jobId = '' } = useParams()
  const { state, reload } = useReceipt(siteId, jobId)
  // Only for the tab title: if the site cannot be loaded, the title is just "Receipt".
  const site = useSite(siteId).state
  usePageTitle(site.status === 'ready' ? `Receipt - ${site.data.site.name}` : 'Receipt')
  return (
    <div className="receipt-page">
      <p className="eyebrow">Water receipt · {jobId}</p>
      <h1>Your receipt</h1>
      {state.status === 'loading' ? <Spinner label="Loading your receipt…" lines={5} /> : null}
      {state.status === 'error' ? (
        <Banner kind="error" actionLabel="Try again" onAction={reload}>
          {state.message}
        </Banner>
      ) : null}
      {state.status === 'ready' ? <ReceiptView receipt={state.data} siteId={siteId} /> : null}
    </div>
  )
}
