/**
 * HTTP adapter — talks to the FastAPI parity endpoints (brief §7) with the
 * magic-link session cookie forwarded server-side. These endpoints do not
 * exist yet (flagged gap on W1.1, to be built in S6.x); the paths below are
 * the contract the API card should satisfy. Selected when MCPFORWORK_API_URL
 * is set.
 */
import { cookies } from "next/headers";
import type { Api } from "./types";

const TIMEOUT_MS = 10_000;

async function call<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const cookie = (await cookies()).toString();
  const res = await fetch(`${base}${path}`, {
    ...init,
    // Forward the session cookie server-side; no client-side token. Narrow to
    // the named session cookie once S6.1 defines it (recorded on the card).
    headers: { cookie, "content-type": "application/json", ...init?.headers },
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export function httpApi(rawBase: string): Api {
  const base = rawBase.replace(/\/+$/, ""); // no trailing slash → no `//v1/...`
  const get = <T>(p: string) => call<T>(base, p);
  const post = <T>(p: string, body?: unknown) =>
    call<T>(base, p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

  // 404 → null, matching the fixtures adapter and the MatchDetail | null
  // signature (a missing match is not an error the page should throw on).
  const getOrNull = async <T>(p: string): Promise<T | null> => {
    const cookie = (await cookies()).toString();
    const res = await fetch(`${base}${p}`, {
      headers: { cookie },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`API ${p} → ${res.status}`);
    return (await res.json()) as T;
  };

  return {
    getProfile: () => get("/v1/profile"),
    listPipeline: () => get("/v1/pipeline"),
    getPipelineStats: () => get("/v1/pipeline/stats"),
    getMatch: (id) => getOrNull(`/v1/matches/${encodeURIComponent(id)}`),
    getConnection: () => get("/v1/connection"),
    getSubscription: () => get("/v1/subscription"),
    listSessions: () => get("/v1/sessions"),
    listAudit: () => get("/v1/audit"),

    createBillingSession: (kind) => post("/v1/billing/session", { kind }),
    approveMatch: (id) => post(`/v1/matches/${encodeURIComponent(id)}/approve`),
    discardMatch: (id) => post(`/v1/matches/${encodeURIComponent(id)}/discard`),
    restoreMatch: (id) => post(`/v1/matches/${encodeURIComponent(id)}/restore`),
    recordOutcome: (id, outcome) => post(`/v1/matches/${encodeURIComponent(id)}/outcome`, { outcome }),
    updateProfile: (patch) => post("/v1/profile", patch),
    requestMagicLink: (email) => post("/v1/auth/magic-link", { email }),
    revokeSession: (id) => post(`/v1/sessions/${encodeURIComponent(id)}/revoke`),
    requestExport: () => post("/v1/account/export"),
    deleteAccount: () => post("/v1/account/delete"),
  };
}
