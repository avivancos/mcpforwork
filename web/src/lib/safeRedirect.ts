/**
 * Guard for billing redirects. The checkout/portal URL comes from our own API,
 * but we only ever navigate to it if it's an https Stripe URL — so a
 * misconfigured or compromised response can't turn `window.location.assign`
 * into an open-redirect. (Closes the W1.1 BillingActions sink note.)
 */
const ALLOWED_BILLING_HOSTS = new Set(["checkout.stripe.com", "billing.stripe.com"]);

export function isSafeBillingUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && ALLOWED_BILLING_HOSTS.has(u.hostname);
  } catch {
    return false;
  }
}
