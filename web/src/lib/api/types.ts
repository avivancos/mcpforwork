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
  /** Non-null once an application exists. 1.0 is supervised-only. */
  consent: "supervised" | null;
  updated: string; // humanized: "25 min ago", "Yesterday"
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

  /** Stripe checkout/portal session — returns null until S7.1 lands (fixtures). */
  createBillingSession(kind: "checkout" | "portal"): Promise<{ url: string | null }>;
  approveMatch(id: string): Promise<void>;
  discardMatch(id: string): Promise<void>;
  restoreMatch(id: string): Promise<void>;
  recordOutcome(id: string, outcome: Outcome): Promise<void>;
  updateProfile(patch: Partial<Profile>): Promise<void>;
  requestMagicLink(email: string): Promise<void>;
  revokeSession(id: string): Promise<void>;
  requestExport(): Promise<void>;
  deleteAccount(): Promise<void>;
}
