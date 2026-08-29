import { readFileSync } from "node:fs";

const lock = JSON.parse(readFileSync(process.argv[2], "utf8"));
for (const [path, metadata] of Object.entries(lock.packages ?? {})) {
  if (!path.startsWith("node_modules/") || !metadata.version) continue;
  process.stdout.write(`${path.slice("node_modules/".length)}\t${metadata.version}\n`);
}
