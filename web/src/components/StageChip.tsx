import type { Stage } from "@/lib/api/types";

const MAP: Record<Stage, { label: string; variant: string }> = {
  new_match: { label: "new match", variant: "" },
  filling: { label: "filling", variant: "chip--indigo" },
  awaiting_you: { label: "awaiting you", variant: "chip--amber" },
  submitted: { label: "submitted", variant: "chip--indigo" },
  verified: { label: "verified", variant: "chip--green" },
  interview: { label: "interview", variant: "chip--green" },
  offer: { label: "offer", variant: "chip--green" },
  rejected: { label: "rejected", variant: "chip--faded" },
  no_response: { label: "no response", variant: "" },
  discarded: { label: "discarded", variant: "chip--faded" },
};

export function StageChip({ stage, size = 10 }: { stage: Stage; size?: number }) {
  // Fallback keeps a row rendering if a real backend ever sends a stage the UI
  // doesn't know yet, instead of crashing on an undefined MAP entry.
  const { label, variant } = MAP[stage] ?? { label: String(stage).replace(/_/g, " "), variant: "" };
  return (
    <span className={`chip ${variant}`} style={{ fontSize: size }}>
      {label}
    </span>
  );
}
