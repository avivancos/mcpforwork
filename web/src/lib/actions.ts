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

export async function restoreMatch(id: string): Promise<void> {
  await api.restoreMatch(id);
  revalidatePath("/pipeline");
  revalidatePath(`/matches/${id}`);
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

export async function requestExport(): Promise<void> {
  await api.requestExport();
  revalidatePath("/account/data");
}

export async function deleteAccount(): Promise<void> {
  await api.deleteAccount();
  revalidatePath("/account/data");
}
