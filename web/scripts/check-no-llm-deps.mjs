#!/usr/bin/env node
// Structural invariant (PRODUCT_PLAN §Core thesis 1, brief §2): zero LLM SDKs
// anywhere in the web dependency tree. Mirrors the Python import-linter rule
// that bans `openai`/`anthropic` from domain/services. Fails CI on violation.
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// Package names (or scope prefixes ending in "/") that must never appear.
const BANNED = [
  "openai",
  "anthropic",
  "@anthropic-ai/",
  "@openai/",
  "@google/generative-ai", // legacy Google SDK
  "@google/genai", // current Google GenAI SDK
  "ai", // Vercel AI SDK
  "@ai-sdk/",
  "langchain",
  "@langchain/",
  "llamaindex",
  "cohere-ai",
  "@mistralai/",
  "ollama",
  "groq-sdk",
];

const matches = (name) =>
  BANNED.some((b) => (b.endsWith("/") ? name.startsWith(b) : name === b));

const offenders = new Set();

// 1. Direct dependencies in package.json (all groups). Check both the
//    declared name AND the spec value, so an alias (`"x": "npm:openai@4"`)
//    that hides a banned package behind a benign key is caught.
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
for (const group of ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"]) {
  for (const [name, spec] of Object.entries(pkg[group] ?? {})) {
    if (matches(name)) offenders.add(`package.json ${group}: ${name}`);
    const alias = typeof spec === "string" && spec.match(/^npm:(@?[^@]+)/)?.[1];
    if (alias && matches(alias)) offenders.add(`package.json ${group} (aliased): ${name} → ${alias}`);
  }
}

// 2. The full resolved graph in package-lock.json (transitive deps included).
//    The lockfile is required — silently checking only direct deps would let a
//    transitive LLM SDK through, defeating the point of the guard.
const lockPath = join(root, "package-lock.json");
if (!existsSync(lockPath)) {
  console.error("package-lock.json is missing — cannot verify the transitive dependency graph. Run `npm install`.");
  process.exit(1);
}
{
  const lock = JSON.parse(readFileSync(lockPath, "utf8"));
  for (const [path, entry] of Object.entries(lock.packages ?? {})) {
    if (path === "") continue;
    // Match both the install path's package name AND the resolved `name`
    // field — the latter catches npm aliases (`"x": "npm:ai@3"`), where the
    // path key is the alias but `entry.name` is the real (banned) package.
    const pathName = path.replace(/^.*node_modules\//, "");
    const resolvedName = entry?.name;
    if (matches(pathName)) offenders.add(`package-lock.json: ${pathName}`);
    if (resolvedName && matches(resolvedName))
      offenders.add(`package-lock.json (aliased): ${pathName} → ${resolvedName}`);
  }
}

if (offenders.size > 0) {
  console.error("LLM SDK found in the web dependency tree — this violates a product invariant:");
  for (const o of offenders) console.error(`  - ${o}`);
  process.exit(1);
}
console.log("check:no-llm-deps OK — no LLM SDKs in the dependency tree.");
