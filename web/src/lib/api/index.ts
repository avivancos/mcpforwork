/**
 * The single API seam (ADR 0002): HTTP adapter when MCPFORWORK_API_URL is
 * set, fixtures (Sofía Reyes demo dataset) otherwise. Swapping to the real
 * backend is a config change, not a UI change.
 *
 * Fail closed: a production deploy that loses MCPFORWORK_API_URL must NOT
 * silently degrade into the fictional demo behind what will be a real login.
 * Fixtures in production require an explicit MCPFORWORK_FIXTURES=1 opt-in
 * (keeps the public demo deployable while making the fallback deliberate).
 */
import { fixturesApi } from "./fixtures";
import { httpApi } from "./http";
import type { Api } from "./types";

const base = process.env.MCPFORWORK_API_URL;
const fixturesOptIn = process.env.MCPFORWORK_FIXTURES === "1";
// `next build` imports this module to read route config; the env need not be
// present then (routes are force-dynamic, resolved per request). Fail closed
// only when a real server process boots without it.
const isBuildPhase = process.env.NEXT_PHASE === "phase-production-build";

if (!base && process.env.NODE_ENV === "production" && !fixturesOptIn && !isBuildPhase) {
  throw new Error(
    "MCPFORWORK_API_URL is required in production. " +
      "Set it to the FastAPI base URL, or set MCPFORWORK_FIXTURES=1 to run the demo dataset deliberately.",
  );
}

/** True when the UI is backed by the in-memory demo data, not a real API. */
export const usingFixtures = !base;

export const api: Api = base ? httpApi(base) : fixturesApi;

export * from "./types";
