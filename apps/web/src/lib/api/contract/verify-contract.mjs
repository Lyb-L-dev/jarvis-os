/**
 * Contract consistency check (Sprint 4, Frontend API Layer).
 *
 * Two assertions:
 *  1. Export-surface parity: the public exports of lib/api.ts (compat layer)
 *     must exactly match the frozen snapshot in expected-exports.json.
 *  2. Path alignment (C2): every API path referenced by lib/api/** must exist
 *     in the backend FastAPI router endpoints (methods + normalized paths),
 *     so front-end/back-end contract drift is caught at CI time.
 *
 * Run from apps/web:
 *   node src/lib/api/contract/verify-contract.mjs
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.join(__dirname, "..", "..", "..", "..");
const REPO_ROOT = path.join(WEB_ROOT, "..", "..");
const API_DIR = path.join(WEB_ROOT, "src", "lib", "api");
const ROUTES_DIR = path.join(REPO_ROOT, "apps", "api", "app", "api", "routes");
const ROUTER_FILE = path.join(REPO_ROOT, "apps", "api", "app", "api", "router.py");
const SNAPSHOT_FILE = path.join(API_DIR, "contract", "expected-exports.json");

let failures = 0;

function fail(message) {
  failures += 1;
  console.error(`  FAIL ${message}`);
}

function ok(message) {
  console.log(`  ok   ${message}`);
}

function read(file) {
  return fs.readFileSync(file, "utf8");
}

function exportNameFromLine(line) {
  const m = line.match(
    /^export (?:async )?(?:function|const|type|interface|class|enum)\s+([A-Za-z_$][\w$]*)/,
  );
  return m ? m[1] : null;
}

function publicExports() {
  const names = new Set();
  const compat = read(path.join(WEB_ROOT, "src", "lib", "api.ts"));
  for (const m of compat.matchAll(/^export \{ (\w+) \} from/gm)) {
    names.add(m[1]);
  }
  const files = fs
    .readdirSync(API_DIR)
    .filter((f) => f.endsWith(".ts"))
    .filter((f) => f !== "client.ts")
    .sort();
  for (const file of files) {
    const content = read(path.join(API_DIR, file));
    for (const line of content.split("\n")) {
      const name = exportNameFromLine(line);
      if (name) names.add(name);
    }
  }
  return names;
}

function checkExports() {
  console.log("1) Export-surface parity (lib/api.ts public exports vs frozen snapshot)");
  const snapshot = JSON.parse(read(SNAPSHOT_FILE)).exports;
  const current = [...publicExports()].sort();
  const missing = snapshot.filter((n) => !current.includes(n));
  const extra = current.filter((n) => !snapshot.includes(n));
  if (missing.length === 0 && extra.length === 0 && snapshot.length === current.length) {
    ok(`${snapshot.length} exports unchanged (${current.length} verified)`);
    return;
  }
  if (missing.length) fail(`missing exports: ${missing.join(", ")}`);
  if (extra.length) fail(`unexpected exports: ${extra.join(", ")}`);
  if (snapshot.length !== current.length) {
    fail(`count mismatch: snapshot=${snapshot.length} current=${current.length}`);
  }
}

function frontendPaths() {
  const entries = []; // {method, path, source}
  const files = fs
    .readdirSync(API_DIR)
    .filter((f) => f.endsWith(".ts"))
    .filter((f) => f !== "client.ts")
    .sort();
  for (const file of files) {
    const content = read(path.join(API_DIR, file));
    const blocks = content.split(/^(?=export (?:async )?function |(?:async )?function )/m);
    for (const block of blocks) {
      const urls = [
        ...block.matchAll(/\$\{API_BASE_URL\}([^`]*)/g),
      ];
      if (urls.length === 0) continue;
      const methodMatch = block.match(/method:\s*"(GET|POST|PUT|PATCH|DELETE)"/);
      let method = methodMatch ? methodMatch[1] : "GET";
      if (!methodMatch && block.includes("consumeChatStream(")) {
        method = "POST";
      }
      const actionMatch = block.match(
        /\b(?:action|decision):\s*((?:"[^"]*"\s*\|\s*)+"[^"]*")/,
      );
      const actions = actionMatch
        ? [...actionMatch[1].matchAll(/"([^"]*)"/g)].map((m) => m[1])
        : [];
      for (const m of urls) {
        const raw = m[1];
        const normalized = raw
          .replace(/\$\{[^}]*\}/g, "{}")
          .split("?")[0]
          .replace(/\/+/g, "/");
        const candidates = [normalized];
        if (normalized.endsWith("/{}")) {
          candidates.push(normalized.slice(0, -3));
        } else if (normalized.endsWith("{}")) {
          candidates.push(normalized.slice(0, -2).replace(/\/+$/, ""));
        }
        const funcName = block.match(/function\s+([A-Za-z_$][\w$]*)/)?.[1] ?? "?";
        entries.push({ method, paths: candidates, actions, source: `${file}:${funcName}` });
      }
    }
  }
  return entries;
}

function backendEndpoints() {
  const mount = new Map();
  const routerText = read(ROUTER_FILE);
  const inc = [
    ...routerText.matchAll(
      /include_router\(\s*(\w+)\.router(?:,?\s*prefix="([^"]*)")?/g,
    ),
  ];
  for (const m of inc) {
    mount.set(m[1], m[2] ?? "");
  }
  const endpoints = new Set();
  const files = fs.readdirSync(ROUTES_DIR).filter((f) => f.endsWith(".py"));
  for (const file of files) {
    const moduleName = file.replace(/\.py$/, "");
    const content = read(path.join(ROUTES_DIR, file));
    const prefixMatch = content.match(/APIRouter\(\s*prefix="([^"]*)"/);
    const routerPrefix = prefixMatch ? prefixMatch[1] : "";
    const mountPrefix = mount.get(moduleName) ?? "";
    for (const route of content.matchAll(
      /@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"/g,
    )) {
      const method = route[1].toUpperCase();
      const routePath = route[2];
      const full = `${mountPrefix}${routerPrefix}${routePath}`.replace(/\/+/g, "/");
      const normalized = full.replace(/\{[^}]*\}/g, "{}");
      endpoints.add(`${method} ${normalized}`);
    }
  }
  return endpoints;
}

function checkPaths() {
  console.log("2) Path alignment (lib/api/** paths ⊆ FastAPI router endpoints)");
  const backend = backendEndpoints();
  const frontend = frontendPaths();
  const seen = new Set();
  let checked = 0;
  for (const entry of frontend) {
    const key = `${entry.method} ${entry.paths.join("|")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    checked += 1;
    let matched = entry.paths.some((p) => backend.has(`${entry.method} ${p}`));
    if (!matched && entry.actions.length > 0) {
      matched = entry.paths.some((p) => {
        if (!p.endsWith("/{}")) return false;
        const prefix = p.slice(0, -3);
        return entry.actions.every((a) => backend.has(`${entry.method} ${prefix}/${a}`));
      });
    }
    if (!matched) {
      fail(`${entry.method} ${entry.paths.join(" or ")} not found in backend routers (${entry.source})`);
    }
  }
  ok(`${checked} unique frontend method+path entries checked against ${backend.size} backend endpoints`);
}

checkExports();
checkPaths();

console.log(failures === 0 ? "\nContract check PASSED." : `\nContract check FAILED (${failures} failure(s)).`);
process.exit(failures === 0 ? 0 : 1);
