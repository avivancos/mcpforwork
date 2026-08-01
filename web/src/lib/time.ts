/**
 * Humanize the API's ISO-8601 timestamps for display (W6.1). The seam
 * contract is ISO across the wire; humanization happens at render so every
 * surface speaks one format. Hand-rolled — no date library for one helper.
 * `now` is injectable for tests; unparseable input passes through unchanged
 * (a render must never crash on a bad timestamp).
 */

const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

export function timeAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  const diff = now.getTime() - then.getTime();
  // "just now" spans the whole first minute — [45s, 60s) must never render
  // "0 min ago" (W6.1 review P2). Covers slight clock skew too.
  if (diff < MIN) return "just now";
  if (diff < HOUR) return `${Math.floor(diff / MIN)} min ago`;
  if (diff < DAY) return `${Math.floor(diff / HOUR)} hr ago`;
  if (diff < 2 * DAY) return "Yesterday";
  if (diff < 7 * DAY) return `${Math.floor(diff / DAY)} days ago`;
  const sameYear = then.getFullYear() === now.getFullYear();
  return `${then.getDate()} ${MONTHS[then.getMonth()]}${sameYear ? "" : ` ${then.getFullYear()}`}`;
}
