// Sprint 4 QA: run every verify_*.cjs acceptance script and record results.
// Usage: node scripts/verify_regression_suite.cjs
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const SCRIPTS_DIR = path.join(__dirname);
const RESULT_PATH = path.join(__dirname, "..", ".runtime", "qa-s4-verify-results.json");
const TIMEOUT_MS = 180000;

const scripts = fs
  .readdirSync(SCRIPTS_DIR)
  .filter(
    (name) =>
      /^verify_.*\.cjs$/.test(name) &&
      name !== "verify_regression_suite.cjs" &&
      name !== "verify_visual_baseline.cjs",
  )
  .sort();

const results = [];
for (const name of scripts) {
  const started = Date.now();
  const outcome = spawnSync(process.execPath, [path.join(SCRIPTS_DIR, name)], {
    timeout: TIMEOUT_MS,
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
  });
  const elapsedMs = Date.now() - started;
  const status = outcome.signal === "SIGTERM" ? "TIMEOUT" : outcome.status === 0 ? "PASS" : "FAIL";
  const tail = `${(outcome.stdout || "").slice(-600)}${(outcome.stderr || "").slice(-600)}`;
  results.push({ name, status, exitCode: outcome.status, elapsedMs, tail });
  console.log(`[${status}] ${name} (${elapsedMs}ms)`);
}

fs.writeFileSync(RESULT_PATH, JSON.stringify(results, null, 2));
const passed = results.filter((r) => r.status === "PASS").length;
const failed = results.filter((r) => r.status === "FAIL").length;
const timedOut = results.filter((r) => r.status === "TIMEOUT").length;
console.log(`summary: ${passed} passed, ${failed} failed, ${timedOut} timeout (${scripts.length} scripts)`);
console.log(`results -> ${RESULT_PATH}`);
