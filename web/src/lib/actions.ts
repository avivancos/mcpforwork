"use server";

/**
 * Server actions — the only writes the dashboard performs (brief §6:
 * approve/discard, restore, record outcome, profile edits, account
 * management). Each one goes through the API seam and revalidates the
 * affected route. No LLM, no browser automation, no submission of
 * applications — those live in the user's client.
 */
import { revalidatePath } from "next/cache";
import { api, type Outcome, type Profile } from "./api";

export async function approveMatch(id: string): Promise<void> {
  await api.approveMatch(id);
  revalidatePath("/pipeline");
  revalidatePath(`/matches/${id}`);
}

export async function discardMatch(id: string): Promise<void> {
  await api.discardMatch(id);
  revalidatePath("/pipeline");
  revalidatePath(`/matches/${id}`);
}

/**
 * L1 (ADR 0005): approve one application's submit. Takes the application id
 * plus the finding id (for revalidation) — the consent write itself targets
 * the application.
 */
export async function approveSubmit(applicationId: string, findingId: string): Promise<void> {
  await api.approveSubmit(applicationId);
  revalidatePath("/pipeline");
  revalidatePath(`/matches/${findingId}`);
}

export async function restoreMatch(id: string): Promise<void> {
  await api.restoreMatch(id);
  revalidatePath("/pipeline");
  revalidatePath(`/matches/${id}`);
}

// Server actions are public POST endpoints — validate the policy here rather
// than trust the client (same posture as updateProfile). Ranges mirror the
// API's own validation (S7.2b): score 0–100, cap 1–50; JSON booleans are not
// integers.
const isInt = (x: unknown): x is number => typeof x === "number" && Number.isInteger(x);

export async function saveAutopilotPolicy(policy: {
  minScore: number;
  maxPerDay: number;
}): Promise<void> {
  const { minScore, maxPerDay } = policy;
  if (!isInt(minScore) || minScore < 0 || minScore > 100) {
    throw new Error("minScore must be an integer 0–100");
  }
  if (!isInt(maxPerDay) || maxPerDay < 1 || maxPerDay > 50) {
    throw new Error("maxPerDay must be an integer 1–50");
  }
  await api.putAutopilotPolicy({ minScore, maxPerDay });
  revalidatePath("/account/autopilot");
}

export async function revokeAutopilotPolicy(): Promise<void> {
  await api.revokeAutopilotPolicy();
  revalidatePath("/account/autopilot");
}

export async function recordOutcome(id: string, outcome: Outcome): Promise<void> {
  await api.recordOutcome(id, outcome);
  revalidatePath("/pipeline");
  revalidatePath(`/matches/${id}`);
}

// Scalar profile fields the dashboard is allowed to edit. Server actions are
// public POST endpoints and `Partial<Profile>` is compile-time only, so we
// whitelist here rather than trust the client — otherwise arbitrary JSON (e.g.
// `achievements: "x"`) reaches the store and breaks rendering for everyone.
// achievements / styleProfile / tier1Step are set by the client LLM, not here.
const EDITABLE_STRING_FIELDS = [
  "name",
  "email",
  "headline",
  "targetRole",
  "workRights",
  "salaryFloor",
  "languages",
  "seniority",
  "employmentType",
] as const;
const WORK_MODES: ReadonlyArray<Profile["workMode"]> = ["onsite", "hybrid", "remote"];

export async function updateProfile(patch: Partial<Profile>): Promise<void> {
  const clean: Partial<Profile> = {};
  for (const key of EDITABLE_STRING_FIELDS) {
    if (typeof patch[key] === "string") clean[key] = patch[key];
  }
  if (Array.isArray(patch.cities)) {
    clean.cities = patch.cities.filter((c): c is string => typeof c === "string").slice(0, 20);
  }
  if (patch.workMode && WORK_MODES.includes(patch.workMode)) clean.workMode = patch.workMode;
  if (patch.tier1Step && [1, 2, 3, 4].includes(patch.tier1Step)) clean.tier1Step = patch.tier1Step;

  await api.updateProfile(clean);
  revalidatePath("/profile");
  revalidatePath("/onboarding");
}

export async function requestMagicLink(email: string): Promise<void> {
  await api.requestMagicLink(email);
}

export async function createBillingSession(
  kind: "checkout" | "portal",
): Promise<{ url: string | null }> {
  return api.createBillingSession(kind);
}

export async function revokeSession(id: string): Promise<void> {
  await api.revokeSession(id);
  revalidatePath("/account/sessions");
}

export async function requestExport(): Promise<string> {
  const json = await api.requestExport();
  revalidatePath("/account/data");
  return json;
}

export async function deleteAccount(): Promise<void> {
  await api.deleteAccount();
  revalidatePath("/account/data");
}
