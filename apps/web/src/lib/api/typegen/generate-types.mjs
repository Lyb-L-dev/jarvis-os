/**
 * OpenAPI → TypeScript type generation (Sprint 4, Frontend API Layer).
 *
 * Generates apps/web/src/types/generated.ts from the running FastAPI's
 * OpenAPI document using openapi-typescript (devDependency, runtime-free).
 *
 * RUN GATE: the generation needs a live API. When the API is not running the
 * script reports "gated" and exits 0 without touching types/generated.ts.
 * Start the API (scripts/start.ps1) and re-run to backfill:
 *
 *   cd apps/web
 *   node src/lib/api/typegen/generate-types.mjs
 *
 * Override the schema URL with OPENAPI_URL if the API is not on 127.0.0.1:8000.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.join(__dirname, "..", "..", "..", "..");
const OUT_FILE = path.join(WEB_ROOT, "src", "types", "generated.ts");
const SCHEMA_URL =
  process.env.OPENAPI_URL ?? "http://127.0.0.1:8000/openapi.json";

const CLI_PATH = path.join(
  WEB_ROOT,
  "node_modules",
  "openapi-typescript",
  "bin",
  "cli.js",
);

async function main() {
  console.log(`Fetching OpenAPI document from ${SCHEMA_URL} ...`);
  try {
    const res = await fetch(SCHEMA_URL, {
      signal: AbortSignal.timeout(8000),
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    await res.json(); // validates the document before handing off to the CLI
  } catch (err) {
    console.log(
      `[gated] API not reachable (${err.message}). ` +
        "Start the backend API and re-run this script to generate " +
        "src/types/generated.ts.",
    );
    process.exit(0);
  }

  console.log("Generating TypeScript definitions ...");
  await fs.promises.mkdir(path.dirname(OUT_FILE), { recursive: true });
  await execFileAsync(
    process.execPath,
    [CLI_PATH, SCHEMA_URL, "--output", OUT_FILE],
    { cwd: WEB_ROOT },
  );
  console.log(`Wrote ${OUT_FILE}`);
  console.log("Type generation complete.");
}

main().catch((err) => {
  console.error("Type generation failed:", err);
  process.exit(1);
});
