import { expect, test as base, type Page, type Request } from '@playwright/test'

/** Everything a spec may want to know about what the page did on the network and in the console. */
export interface Diagnostics {
  /** console.error messages and uncaught page errors. */
  readonly consoleErrors: string[]
  /** Requests that failed at the network level (DNS, CORS, blocked). */
  readonly failedRequests: string[]
  /** Responses with status >= 400, as "status method url". */
  readonly badResponses: string[]
  /** POST /plan requests seen so far. */
  readonly planRequests: Request[]
  /** Anything the read-only guard refused to send. */
  readonly blockedWrites: string[]
}

interface Fixtures {
  diag: Diagnostics
  /** Always on: aborts and records any write other than POST /plan. */
  readOnlyGuard: undefined
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

function isPlanPost(request: Request): boolean {
  if (request.method() !== 'POST') return false
  return new URL(request.url()).pathname.replace(/\/+$/, '').endsWith('/plan')
}

function attachDiagnostics(page: Page): Diagnostics {
  const diag: Diagnostics = {
    consoleErrors: [],
    failedRequests: [],
    badResponses: [],
    planRequests: [],
    blockedWrites: [],
  }
  page.on('console', (message) => {
    if (message.type() === 'error') diag.consoleErrors.push(`${message.text()} (${message.location().url})`)
  })
  page.on('pageerror', (error) => {
    diag.consoleErrors.push(`pageerror: ${error.message}`)
  })
  page.on('requestfailed', (request) => {
    diag.failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText ?? ''}`)
  })
  page.on('response', (response) => {
    if (response.status() >= 400) {
      diag.badResponses.push(`${response.status()} ${response.request().method()} ${response.url()}`)
    }
  })
  page.on('request', (request) => {
    if (isPlanPost(request)) diag.planRequests.push(request)
  })
  return diag
}

export const test = base.extend<Fixtures>({
  // The callback is named `provide`, not Playwright's usual `use`: oxlint's react-hooks rule
  // mistakes a function called `use` for a React hook.
  diag: async ({ page }, provide) => {
    await provide(attachDiagnostics(page))
  },
  readOnlyGuard: [
    async ({ page, diag }, provide) => {
      await page.route('**/*', async (route) => {
        const request = route.request()
        if (SAFE_METHODS.has(request.method()) || isPlanPost(request)) {
          await route.continue()
          return
        }
        diag.blockedWrites.push(`${request.method()} ${request.url()}`)
        await route.abort('blockedbyclient')
      })
      await provide(undefined)
      expect(diag.blockedWrites, 'the suite is read-only: nothing but GET and POST /plan may be sent').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }
