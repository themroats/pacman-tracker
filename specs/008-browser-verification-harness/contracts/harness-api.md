# Contract: Playwright Harness Helpers (TypeScript)

**Feature**: `008-browser-verification-harness` | **Date**: 2026-06-15

The reusable scaffold under `frontend/tests/e2e/helpers/`. These are the stable interfaces an agent or a saved spec uses to reach protected pages, force error responses, and capture evidence. Names are indicative; signatures define the contract.

---

## `auth.ts` — seed authenticated session

```ts
export interface DemoAuth {
  accessToken: string;   // placeholder; bypass ignores it server-side
  userId: string;        // demo user id ("1")
  displayName: string;   // "Demo Runner"
}

/**
 * Seed the frontend auth state into localStorage BEFORE navigation so the
 * app treats the session as authenticated and does not redirect to login.
 * Keys MUST match the app store: access_token, user_id, display_name.
 */
export async function seedAuth(page: Page, auth?: Partial<DemoAuth>): Promise<void>;
```
- **Contract**: writes `localStorage.access_token`, `localStorage.user_id`, `localStorage.display_name` using the exact keys the app reads (`frontend/src/store/index.ts`).
- **Postcondition**: navigating to a protected route renders it without redirecting to the Strava login screen (FR-003, US1 scenario 1).

---

## `intercept.ts` — force backend responses at the browser layer

```ts
export interface ForcedResponse {
  urlPattern: string;          // glob, e.g. "**/api/v1/coverage**"
  status: number;              // 401 | 503 | 404 | ...
  body?: unknown;              // JSON body matching the endpoint schema
}

/** Install a browser-layer route handler that fulfills matching requests
 *  with the synthetic response. Backend is never contacted for these. */
export async function forceResponse(page: Page, scenario: ForcedResponse): Promise<void>;

/** Convenience presets for the 3 priority error states. */
export const ErrorPresets: {
  sessionExpired(urlPattern: string): ForcedResponse;     // 401
  routingUnavailable(urlPattern: string): ForcedResponse; // 503
  notFound(urlPattern: string): ForcedResponse;           // 404 / empty
};
```
- **Contract**: uses Playwright `page.route()` to fulfill; does NOT modify the backend (FR-008).
- **Postcondition**: the targeted page action displays the matching user-facing error UI (US3).

---

## `evidence.ts` — capture verification evidence and produce a result

```ts
export interface NetworkOutcome {
  url: string;
  method: string;
  status: number;
  ok: boolean;
}

export interface VerificationEvidence {
  pageText: string;            // visible content snapshot
  consoleErrors: string[];     // captured console.error / page errors
  network: NetworkOutcome[];   // request→response outcomes relevant to the action
  screenshotPath?: string;
}

export type Outcome = "pass" | "fail";

export interface VerificationResult {
  outcome: Outcome;
  expected: boolean;           // true = expected UI appeared; false = unexpected error
  evidence: VerificationEvidence;
  notes?: string;
}

/** Begin collecting console errors + network outcomes for the page. */
export function startEvidence(page: Page): () => VerificationEvidence;

/** Assemble a pass/fail result from evidence + an assertion predicate. */
export function makeResult(
  evidence: VerificationEvidence,
  assertion: (e: VerificationEvidence) => boolean,
  notes?: string
): VerificationResult;
```
- **Contract**: captures page content, user-facing/console errors, and backend interaction outcomes (FR-006); produces a clear pass/fail distinguishing expected vs. unexpected (FR-007).
- **Agent use**: an agent calls `seedAuth` → navigate → (optional `forceResponse`) → act → `makeResult`, then reports outcome + evidence without any human login step (SC-007, FR-014).

---

## Configuration contract — `playwright.config.ts`

- `baseURL`: `http://localhost:5173` (frontend dev server from `verify-up`).
- Projects: headless (default, agent) and headed (developer) variants.
- `use.trace`/`screenshot`: on failure, to support evidence capture.
- Test dir: `frontend/tests/e2e`. Promotable specs (`*.spec.ts`) live beside helpers.
