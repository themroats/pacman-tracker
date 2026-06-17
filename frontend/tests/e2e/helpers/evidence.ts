import type { ConsoleMessage, Page, Request, Response } from "@playwright/test";

/**
 * Verification evidence + result helpers (feature 008).
 *
 * Captures what a verification run observed — visible page content, console
 * errors, and backend interaction outcomes — and assembles a clear pass/fail
 * result that distinguishes an expected outcome from an unexpected failure.
 */

export interface NetworkOutcome {
  url: string;
  method: string;
  status: number;
  ok: boolean;
}

export interface VerificationEvidence {
  pageText: string;
  consoleErrors: string[];
  network: NetworkOutcome[];
}

export type Outcome = "pass" | "fail";

export interface VerificationResult {
  outcome: Outcome;
  /** true = the expected UI appeared; false = an unexpected error occurred. */
  expected: boolean;
  evidence: VerificationEvidence;
  notes?: string;
}

/**
 * Begin collecting console errors and backend (api) network outcomes for the
 * page. Returns a finalizer that snapshots the current visible text and the
 * collected signals into a {@link VerificationEvidence} object.
 */
export function startEvidence(page: Page): () => Promise<VerificationEvidence> {
  const consoleErrors: string[] = [];
  const network: NetworkOutcome[] = [];

  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  };
  const onPageError = (err: Error) => {
    consoleErrors.push(err.message);
  };
  const onResponse = (res: Response) => {
    const req: Request = res.request();
    const url = res.url();
    // Only record backend interactions relevant to the action under test.
    if (url.includes("/api/")) {
      network.push({
        url,
        method: req.method(),
        status: res.status(),
        ok: res.ok(),
      });
    }
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  page.on("response", onResponse);

  return async (): Promise<VerificationEvidence> => {
    page.off("console", onConsole);
    page.off("pageerror", onPageError);
    page.off("response", onResponse);
    const pageText = await page.evaluate(() => document.body.innerText);
    return { pageText, consoleErrors, network };
  };
}

/**
 * Assemble a pass/fail result from captured evidence and an assertion predicate.
 *
 * `outcome` is "pass" only when the assertion holds. `expected` reflects whether
 * the assertion's intended UI/state appeared, so a caller can tell "expected
 * error UI appeared" apart from "an unexpected error occurred".
 */
export function makeResult(
  evidence: VerificationEvidence,
  assertion: (e: VerificationEvidence) => boolean,
  notes?: string,
): VerificationResult {
  const expected = assertion(evidence);
  return {
    outcome: expected ? "pass" : "fail",
    expected,
    evidence,
    notes,
  };
}
