/**
 * `timeAgo` turns the API's ISO-8601 timestamps into the humanized strings
 * the dashboard renders ("25 min ago", "Yesterday"). The seam contract is
 * ISO across the wire (both adapters); humanization happens at render (W6.1).
 * Uses only Node stdlib (`node:test` + `node:assert`, zero new deps); run
 * with `npm test`. Time is INJECTED via `now` — never patched.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { timeAgo } from "./time.ts";

const NOW = new Date("2026-08-02T12:00:00.000Z");
const ago = (ms: number) => new Date(NOW.getTime() - ms).toISOString();

test("the whole first minute renders as just now — never 0 min ago", () => {
  assert.equal(timeAgo(ago(0), NOW), "just now");
  assert.equal(timeAgo(ago(44_000), NOW), "just now");
  assert.equal(timeAgo(ago(50_000), NOW), "just now"); // [45s,60s) window
  assert.equal(timeAgo(ago(59_999), NOW), "just now");
});

test("under an hour renders whole minutes", () => {
  assert.equal(timeAgo(ago(60_000), NOW), "1 min ago");
  assert.equal(timeAgo(ago(25 * 60_000), NOW), "25 min ago");
  assert.equal(timeAgo(ago(59 * 60_000), NOW), "59 min ago");
});

test("under a day renders whole hours", () => {
  assert.equal(timeAgo(ago(60 * 60_000), NOW), "1 hr ago");
  assert.equal(timeAgo(ago(3 * 3_600_000), NOW), "3 hr ago");
  assert.equal(timeAgo(ago(23 * 3_600_000), NOW), "23 hr ago");
});

test("yesterday is named, not counted in hours", () => {
  assert.equal(timeAgo(ago(24 * 3_600_000), NOW), "Yesterday");
  assert.equal(timeAgo(ago(47 * 3_600_000), NOW), "Yesterday");
});

test("under a week renders days", () => {
  assert.equal(timeAgo(ago(2 * 86_400_000), NOW), "2 days ago");
  assert.equal(timeAgo(ago(6 * 86_400_000), NOW), "6 days ago");
});

test("a week or older renders an absolute date", () => {
  assert.equal(timeAgo(ago(7 * 86_400_000), NOW), "26 Jul");
  assert.equal(timeAgo("2025-12-31T00:00:00.000Z", NOW), "31 Dec 2025");
});

test("unparseable input passes through unchanged rather than crashing render", () => {
  assert.equal(timeAgo("not a date", NOW), "not a date");
});

test("slight clock skew (future timestamp) renders as just now", () => {
  assert.equal(timeAgo(ago(-5_000), NOW), "just now");
});

test("Postgres-flavoured ISO with offset parses too", () => {
  // psycopg serialises timestamptz as +00:00, not Z — both must work.
  assert.equal(timeAgo("2026-08-02T11:35:00.123456+00:00", NOW), "24 min ago");
  assert.equal(timeAgo("2026-08-01T12:00:00+00:00", NOW), "Yesterday");
});
