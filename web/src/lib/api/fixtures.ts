/**
 * Fixtures adapter — the Sofía Reyes seed dataset from the design handoff.
 * Active when MCPFORWORK_API_URL is unset (ADR 0002): every brief-§7 parity
 * endpoint is still a flagged gap on the W1.1 card. Mutations act on an
 * in-memory store so the UI's real code paths (server actions → seam →
 * revalidate) are exercised end-to-end in dev/demo.
 */
import type {
  Api,
  AuditEntry,
  Connection,
  MatchDetail,
  Outcome,
  PipelineItem,
  PipelineStats,
  Profile,
  SessionInfo,
  Stage,
} from "./types";

const profileSeed: Profile = {
  name: "Sofía Reyes",
  email: "sofia.reyes@gmail.com",
  headline: "ICU Nurse · 6 yrs · Madrid",
  targetRole: "ICU / Critical care nurse",
  cities: ["Dublin", "Cork"],
  workRights: "EU citizen — no visa needed",
  salaryFloor: "€52,000 / year",
  workMode: "onsite",
  languages: "Spanish (native) · English (C1)",
  seniority: "Senior",
  employmentType: "Full-time",
  achievements: [
    { id: "a1", text: "6 years ICU, Hospital La Paz (Madrid)", source: "CV" },
    {
      id: "a2",
      text: "Cut ventilator-associated events 23% in 12 months",
      source: "Achievement #2",
    },
    {
      id: "a3",
      text: "NMBI registration in progress — decision Aug",
      source: "Confirmed answer",
    },
  ],
  styleProfile: "Warm, direct, concrete — from a writing sample (email, 2026-06)",
  tier1Step: 2,
};

interface Row extends PipelineItem {
  detail: Omit<MatchDetail, keyof PipelineItem>;
}

const detailDefaults = (over: Partial<Row["detail"]> = {}): Row["detail"] => ({
  pack: "healthcare-ie",
  employmentType: "Full-time",
  postingUrl: "https://careers.example.ie/posting",
  constraintChecks: [
    { label: "EU work rights", ok: true },
    { label: "salary floor", ok: true },
    { label: "English C1", ok: true },
    { label: "relocation", ok: true },
  ],
  dedup: "Not seen before — checked against 214 tracked postings.",
  assets: [],
  audit: [],
  ...over,
});

// ISO-8601 across the seam like the real API (W6.1); the UI humanizes at
// render. Relative to module load so the demo always looks fresh.
const isoAgo = (ms: number) => new Date(Date.now() - ms).toISOString();
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

const rowsSeed: Row[] = [
  {
    id: "m_8k3d",
    fit: 91,
    role: "ICU Staff Nurse",
    company: "Mater Private",
    city: "Dublin",
    stage: "awaiting_you",
    consent: "supervised",
    updated: isoAgo(25 * MIN),
    needsYou: "Draft ready · facts-checked · paused 25 min ago",
    detail: detailDefaults({
      postingUrl: "https://careers.materprivate.ie/apply/icu-staff-nurse",
      assets: [
        { id: "as1", name: "resume—mater—icu.pdf", kind: "resume", note: "tailored · facts-checked" },
        { id: "as2", name: "cover—mater—icu.md", kind: "cover", note: "draft v2 · in your voice" },
      ],
      audit: [
        { at: isoAgo(2 * HOUR), event: "start_application — preflight passed (dedup, cap, playbook)" },
        { at: isoAgo(118 * MIN), event: "request_submit — consent L0, paused for human" },
      ],
    }),
  },
  {
    id: "m_7q2f",
    fit: 86,
    role: "Staff Nurse, Critical Care",
    company: "St Vincent's UH",
    city: "Dublin",
    stage: "submitted",
    consent: "supervised",
    updated: isoAgo(26 * HOUR),
    detail: detailDefaults({
      audit: [
        { at: isoAgo(26 * HOUR), event: "request_submit — L0 approved by you" },
        { at: isoAgo(26 * HOUR - 3 * MIN), event: "confirm_submitted — evidence recorded" },
      ],
    }),
  },
  {
    id: "m_5r9a",
    fit: 84,
    role: "ICU Nurse, Nights",
    company: "Beacon Hospital",
    city: "Sandyford",
    stage: "verified",
    consent: "supervised",
    updated: isoAgo(2 * DAY),
    detail: detailDefaults({
      audit: [{ at: isoAgo(2 * DAY), event: "verify — confirmation email present" }],
    }),
  },
  {
    id: "m_3t7c",
    fit: 78,
    role: "Critical Care Nurse",
    company: "Tallaght University Hospital",
    city: "Dublin",
    stage: "new_match",
    consent: null,
    updated: isoAgo(HOUR),
    detail: detailDefaults(),
  },
  {
    id: "m_2w4e",
    fit: 74,
    role: "Staff Nurse — ICU/HDU",
    company: "Blackrock Clinic",
    city: "Dublin",
    stage: "new_match",
    consent: null,
    updated: isoAgo(HOUR),
    detail: detailDefaults(),
  },
  {
    id: "m_6y1b",
    fit: 76,
    role: "ICU Nurse",
    company: "Hermitage Clinic",
    city: "Lucan",
    stage: "interview",
    consent: "supervised",
    updated: isoAgo(3 * DAY),
    detail: detailDefaults({
      audit: [{ at: isoAgo(3 * DAY), event: "record_outcome — interview scheduled" }],
    }),
  },
  {
    id: "m_1z8h",
    fit: 68,
    role: "Paediatric ICU Nurse",
    company: "Children's Health Ireland",
    city: "Dublin",
    stage: "discarded",
    consent: null,
    updated: isoAgo(4 * DAY),
    detail: detailDefaults(),
  },
  {
    id: "m_9v5j",
    fit: 82,
    role: "Staff Nurse, Critical Care",
    company: "St James's Hospital",
    city: "Dublin",
    stage: "awaiting_you",
    consent: "supervised",
    updated: isoAgo(HOUR),
    needsYou: "2 screening questions need your answer",
    detail: detailDefaults({
      audit: [{ at: isoAgo(HOUR), event: "resolve_field — 2 ask_user fields pending" }],
    }),
  },
];

const sessionsSeed: SessionInfo[] = [
  { id: "s1", device: "This browser · macOS · Dublin", lastSeen: isoAgo(0), current: true },
  { id: "s2", device: "iPhone · Safari", lastSeen: isoAgo(2 * DAY), current: false },
];

const auditSeed: AuditEntry[] = [
  { at: isoAgo(118 * MIN), event: "request_submit (L0) — ICU Staff Nurse, Mater Private" },
  { at: isoAgo(26 * HOUR), event: "confirm_submitted — Staff Nurse, St Vincent's UH" },
  { at: isoAgo(3 * DAY), event: "profile updated — salary floor (private)" },
  { at: isoAgo(4 * DAY), event: "connector granted — Claude (scopes: read/write, your data)" },
];

/**
 * The store lives on globalThis: Next bundles this module separately into the
 * page's RSC chunk and each route's server-action chunk, so plain module
 * state would exist twice and mutations from actions would never be seen by
 * renders. One process-wide instance fixes that (same pattern as dev DB
 * client singletons).
 */
interface FixtureStore {
  profile: Profile;
  rows: Row[];
  sessions: SessionInfo[];
  audit: AuditEntry[];
}

const g = globalThis as typeof globalThis & { __mcpforworkFixtures?: FixtureStore };
const store: FixtureStore = (g.__mcpforworkFixtures ??= {
  profile: profileSeed,
  rows: rowsSeed,
  sessions: sessionsSeed,
  audit: auditSeed,
});
const { profile, rows, sessions, audit: accountAudit } = store;

const strip = (r: Row): PipelineItem => {
  const { detail: _detail, ...item } = r;
  return item;
};

export const fixturesApi: Api = {
  async getProfile() {
    return profile;
  },
  async listPipeline() {
    return rows.map(strip);
  },
  async getPipelineStats() {
    const by = (s: Stage) => rows.filter((r) => r.stage === s).length;
    return {
      newMatches: { count: by("new_match"), foundThisWeek: 12 },
      needsYou: { count: by("awaiting_you") },
      submitted: { count: by("submitted") + by("verified") + by("interview") + 1, verified: 4 },
      responses: { count: 2, of: 9, interviews: 1 },
    } satisfies PipelineStats;
  },
  async getMatch(id) {
    const row = rows.find((r) => r.id === id);
    return row ? { ...strip(row), ...row.detail } : null;
  },
  async getConnection() {
    return { connected: true, client: "Claude", syncedMinAgo: 2 } satisfies Connection;
  },
  async getSubscription() {
    return { status: "trial", trialDaysLeft: 9, price: "$5/mo" };
  },
  async listSessions() {
    return sessions;
  },
  async listAudit() {
    return accountAudit;
  },

  async createBillingSession() {
    // Stripe is an S7.1 gap — the UI states this honestly instead of faking a flow.
    return { url: null };
  },
  async approveMatch(id) {
    const r = rows.find((x) => x.id === id);
    if (r && r.stage === "new_match") {
      r.stage = "filling";
      r.consent = "supervised";
      r.updated = isoAgo(0);
    }
  },
  async discardMatch(id) {
    const r = rows.find((x) => x.id === id);
    if (r && (r.stage === "new_match" || r.stage === "filling")) {
      r.stage = "discarded";
      r.updated = isoAgo(0);
    }
  },
  async restoreMatch(id) {
    const r = rows.find((x) => x.id === id);
    if (r && r.stage === "discarded") {
      r.stage = "new_match";
      r.updated = isoAgo(0);
    }
  },
  async recordOutcome(id, outcome: Outcome) {
    const r = rows.find((x) => x.id === id);
    // Outcomes may only be recorded against an application that reached the
    // employer — never a raw match. Each outcome maps to its own stage so the
    // chip mirrors what the user actually recorded (no rejected→no_response
    // collapse). The real API must enforce this transition server-side.
    if (r && (r.stage === "submitted" || r.stage === "verified" || r.stage === "interview")) {
      r.stage = outcome;
      r.updated = isoAgo(0);
    }
  },
  async updateProfile(patch) {
    Object.assign(profile, patch);
  },
  async requestMagicLink() {
    // no-op in fixtures — S6.1 gap
  },
  async revokeSession(id) {
    const i = sessions.findIndex((s) => s.id === id && !s.current);
    if (i >= 0) sessions.splice(i, 1);
  },
  async requestExport() {
    accountAudit.unshift({ at: isoAgo(0), event: "GDPR export requested" });
    return JSON.stringify({ preview: true, profile, rows: rows.map(strip) }, null, 2);
  },
  async deleteAccount() {
    accountAudit.unshift({ at: isoAgo(0), event: "account deletion requested (pending confirm)" });
  },
};
