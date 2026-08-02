/**
 * Data shapes for the dashboard, typed to the MCP tool contracts
 * (PRODUCT_PLAN §MCP surface). The dashboard is a mirror: it reads state and
 * performs only the low-risk writes (approve/discard, record outcome,
 * profile edits, account management). See ADR 0002.
 */

/** Application state machine (server-side), rendered as stage chips. */
export type Stage =
  | "new_match"
  | "filling"
  | "awaiting_you"
  | "submitted"
  | "verified"
  | "interview"
  | "offer"
  | "rejected"
  | "no_response"
  | "discarded";

export type Outcome = "no_response" | "rejected" | "interview" | "offer";

export interface PipelineItem {
  id: string;
  fit: number;
  role: string;
  company: string;
  city: string;
  stage: Stage;
  /**
   * Non-null once an application exists. Mirrors the application's
   * consent_level: 0 supervised · 1 autopilot_l1 (dashboard-approved submit,
   * S7.2a) · 2 autopilot_l2 (policy-authorized submit, S7.2b).
   */
  consent: "supervised" | "autopilot_l1" | "autopilot_l2" | null;
  /** The active application's id — the approve-submit action's target. */
  applicationId: string | null;
  updated: string; // ISO-8601 across the seam; humanized at render (timeAgo)
  /** Set when stage === "awaiting_you" — why it's paused. */
  needsYou?: string;
}

export interface PipelineStats {
  newMatches: { count: number; foundThisWeek: number };
  needsYou: { count: number };
  submitted: { count: number; verified: number };
  responses: { count: number; of: number; interviews: number };
}

export interface MatchDetail extends PipelineItem {
  pack: string;
  employmentType: string;
  postingUrl: string;
  constraintChecks: { label: string; ok: boolean }[];
  dedup: string;
  assets: { id: string; name: string; kind: "resume" | "cover"; note: string }[];
  audit: { at: string; event: string }[];
}

export interface Achievement {
  id: string;
  text: string;
  source: string; // "CV" | "Achievement #2" | "Confirmed answer"
}

export interface Profile {
  name: string;
  email: string;
  headline: string;
  targetRole: string;
  cities: string[];
  workRights: string;
  salaryFloor: string; // rendered privately, filters only
  workMode: "onsite" | "hybrid" | "remote";
  languages: string;
  seniority: string;
  employmentType: string;
  achievements: Achievement[];
  styleProfile: string | null;
  tier1Step: 1 | 2 | 3 | 4; // 4 = complete
}

export interface Connection {
  connected: boolean;
  client: "Claude" | "ChatGPT" | null;
  syncedMinAgo: number;
}

export interface Subscription {
  status: "trial" | "active";
  trialDaysLeft: number;
  price: string; // "$5/mo"
}

export interface SessionInfo {
  id: string;
  device: string;
  lastSeen: string;
  current: boolean;
}

export interface AuditEntry {
  at: string;
  event: string;
}

/** L2 policy (S7.2b). null = autopilot off, every submit is the human's. */
export interface AutopilotPolicy {
  enabled: boolean;
  minScore: number;
  maxPerDay: number;
  createdAt: string; // ISO-8601 across the seam; humanized at render
  revokedAt: string | null;
}

/** A board whose pack flags it auto_apply_safe (S7.2c curates which). */
export interface AutopilotBoard {
  slug: string;
  name: string;
}

/** Display labels for the consent union — the single vocabulary both the
 * pipeline table and the match detail render (W6.2). */
export const CONSENT_LABELS: Record<NonNullable<PipelineItem["consent"]>, string> = {
  supervised: "Supervised",
  autopilot_l1: "Autopilot L1",
  autopilot_l2: "Autopilot L2",
};

/** The single seam the UI calls — implemented by fixtures or HTTP (ADR 0002). */
export interface Api {
  getProfile(): Promise<Profile>;
  listPipeline(): Promise<PipelineItem[]>;
  getPipelineStats(): Promise<PipelineStats>;
  getMatch(id: string): Promise<MatchDetail | null>;
  getConnection(): Promise<Connection>;
  getSubscription(): Promise<Subscription>;
  listSessions(): Promise<SessionInfo[]>;
  listAudit(): Promise<AuditEntry[]>;
  getAutopilotPolicy(): Promise<AutopilotPolicy | null>;
  /** Boards flagged auto_apply_safe in the packs registry — never hardcoded. */
  getAutopilotBoards(): Promise<AutopilotBoard[]>;

  /** Stripe checkout/portal session — returns null until S7.1 lands (fixtures). */
  createBillingSession(kind: "checkout" | "portal"): Promise<{ url: string | null }>;
  approveMatch(id: string): Promise<void>;
  discardMatch(id: string): Promise<void>;
  /**
   * L1 consent write (ADR 0005): approve the submit of ONE application that
   * is waiting on you. Takes the APPLICATION id (PipelineItem.applicationId).
   * The only consent artifact the dashboard can mint — it never fills or
   * submits.
   */
  approveSubmit(applicationId: string): Promise<void>;
  /**
   * L2 consent write (ADR 0005): record/replace the autopilot policy. The
   * only place a policy is minted — the MCP entrypoint is read-only.
   */
  putAutopilotPolicy(policy: { minScore: number; maxPerDay: number }): Promise<void>;
  revokeAutopilotPolicy(): Promise<void>;
  restoreMatch(id: string): Promise<void>;
  recordOutcome(id: string, outcome: Outcome): Promise<void>;
  updateProfile(patch: Partial<Profile>): Promise<void>;
  requestMagicLink(email: string): Promise<void>;
  revokeSession(id: string): Promise<void>;
  /** The self-host API returns the export inline — the UI downloads it as a file. */
  requestExport(): Promise<string>;
  deleteAccount(): Promise<void>;
}
