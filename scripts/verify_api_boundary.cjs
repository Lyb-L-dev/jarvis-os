// Sprint 4 split-layer static guard: components must only import the frozen
// "@/lib/api" index (or "@/lib/api.ts"), never domain modules under lib/api/.
// Usage: node scripts/verify_api_boundary.cjs
const fs = require("node:fs");
const path = require("node:path");

const WEB_SRC = path.join(__dirname, "..", "apps", "web", "src");
const VIOLATION = /from\s+["']@\/lib\/api\/(?!["'])([a-z-]+)["']/;
const INDEX_OK = /from\s+["']@\/lib\/api["']/;
const LEGACY_OK = /from\s+["']@\/lib\/api\.ts["']/;

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(full);
    return /\.(ts|tsx)$/.test(entry.name) ? [full] : [];
  });
}

const files = walk(path.join(WEB_SRC, "components"));
const violations = [];
for (const file of files) {
  const source = fs.readFileSync(file, "utf8");
  for (const line of source.split("\n")) {
    const match = line.match(VIOLATION);
    if (match) {
      violations.push(
        `${path.relative(WEB_SRC, file)}: ${line.trim().slice(0, 120)}`,
      );
    }
  }
}

if (violations.length > 0) {
  console.error(`API boundary violations (${violations.length}):`);
  for (const violation of violations) console.error(`  ${violation}`);
  process.exit(1);
}

const indexUsers = files.filter((file) => {
  const source = fs.readFileSync(file, "utf8");
  return INDEX_OK.test(source) || LEGACY_OK.test(source);
}).length;
console.log(`api boundary ok: ${files.length} component files scanned, ${indexUsers} use the frozen @/lib/api index`);
