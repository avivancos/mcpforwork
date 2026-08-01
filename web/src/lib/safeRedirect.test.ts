/**
 * Regression guard for the billing open-redirect control (W5.1 gate P1).
 *
 * `isSafeBillingUrl` is the only security check on the checkout money path: it
 * decides whether `window.location.assign` follows a URL returned by the
 * billing API. Its correctness lives in string/URL branching the type system
 * can't express, so it needs a check that re-runs — not a one-time manual
 * matrix. Uses only Node stdlib (`node:test` + `node:assert`, zero new deps);
 * run with `npm test`. Exercises the REAL compiled module.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { isSafeBillingUrl } from "./safeRedirect.ts";

// [input, expected] — the adversarial matrix the W5.1 reviewers converged on.
const CASES: ReadonlyArray<readonly [string, boolean]> = [
  // Allowed: https on an exact Stripe billing host.
  ["https://checkout.stripe.com/c/pay/cs_test_123", true],
  ["https://billing.stripe.com/p/session_abc", true],
  ["https://checkout.stripe.com/pay?session=1#frag", true],
  ["https://CHECKOUT.STRIPE.COM/c/pay", true], // URL lowercases the host.
  ["HTTPS://checkout.stripe.com/pay", true], // URL lowercases the scheme.
  ["https:checkout.stripe.com/pay", true], // special-scheme URL without "//"

  // Rejected: wrong host.
  ["https://evil.com/pay", false],
  ["https://stripe.com/pay", false], // apex is not on the allowlist
  ["https://checkout.stripe.com./pay", false], // trailing-dot FQDN → not an exact match
  ["https://checkout.stripe.com.evil.com/pay", false], // subdomain-suffix glue
  ["https://evilcheckout.stripe.com/pay", false], // lookalike prefix
  ["https://checkout.stripe.com@evil.com/", false], // userinfo → hostname is evil.com

  // Rejected: wrong / dangerous scheme on an otherwise-allowed host.
  ["http://checkout.stripe.com/pay", false],
  ["ftp://checkout.stripe.com/pay", false],
  ["blob:https://checkout.stripe.com/uuid", false], // protocol is blob:
  ["javascript:alert(document.cookie)", false],
  ["data:text/html,<script>alert(1)</script>", false],
  ["file:///etc/passwd", false],

  // Rejected: malformed / relative (no base → URL() throws → caught → false).
  ["//checkout.stripe.com/pay", false],
  ["/account/billing", false],
  ["not a url", false],
  ["", false],
  ["   ", false],
];

test("isSafeBillingUrl only allows https URLs on exact Stripe billing hosts", () => {
  for (const [input, expected] of CASES) {
    assert.equal(
      isSafeBillingUrl(input),
      expected,
      `${JSON.stringify(input)} should be ${expected ? "allowed" : "rejected"}`,
    );
  }
});
