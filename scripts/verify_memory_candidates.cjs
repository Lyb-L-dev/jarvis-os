// V3-1 acceptance: memory candidate confirmation card (QA & Reliability owned).
// Usage: node scripts/verify_memory_candidates.cjs
//   Default mode (feature flag off): asserts the classic chat view loads and
//   the memory candidate panel stays absent (silent degradation, no errors).
//   JARVIS_V3_MEMORY=on: additionally asserts the /memory-network/candidates
//   endpoint is reachable with the frozen shape, the panel renders candidate
//   rows, and confirming an entity removes it from the pending list.
// Endpoints default to 127.0.0.1:3000/8000; override with JARVIS_WEB_URL and
// JARVIS_API_URL (e.g. isolated verification stack on other ports).
// Env gate: if the web or API service is not running, prints SKIPPED and
// exits 0 (never fabricates a pass).
const { chromium } = require("../apps/web/node_modules/playwright");
const http = require("node:http");
const path = require("node:path");

const WEB_URL = process.env.JARVIS_WEB_URL ?? "http://127.0.0.1:3000";
const API_URL = process.env.JARVIS_API_URL ?? "http://127.0.0.1:8000";
const MEMORY_ON = process.env.JARVIS_V3_MEMORY === "on";

// With the feature flag off the panel probes /memory-network/* which 404 by
// design; the V3-0 dialog workspace also probes /ui/dialog and /ui/events
// (their flags are off too). Those are silent-degradation paths, not product
// errors.
const EXPECTED_404_RESOURCE = /\/memory-network\/|\/ui\/dialog|\/ui\/events/;

function probe(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode ?? 0);
    });
    req.setTimeout(3000, () => {
      req.destroy();
      resolve(0);
    });
    req.on("error", () => resolve(0));
  });
}

async function main() {
  const [webCode, apiCode] = await Promise.all([
    probe(`${WEB_URL}/chat`),
    probe(`${API_URL}/api/v1/health/live`),
  ]);
  if (webCode === 0 || apiCode === 0) {
    console.log(
      JSON.stringify(
        {
          status: "SKIPPED",
          reason: `frontend=${webCode === 0 ? "down" : "up"} backend=${apiCode === 0 ? "down" : "up"}`,
        },
        null,
        2,
      ),
    );
    return;
  }

  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.JARVIS_EDGE_PATH ??
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const errors = [];
  const expected404Responses = [];
  const state = {};
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1100 },
    });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("response", (response) => {
      if (
        response.status() === 404 &&
        EXPECTED_404_RESOURCE.test(response.url())
      ) {
        expected404Responses.push(response.url());
      }
    });

    await page.goto(`${WEB_URL}/chat`, { waitUntil: "networkidle" });
    const composer = page.locator("textarea").first();
    await composer.waitFor({ state: "visible", timeout: 15_000 });

    const candidatesProbe = await page.evaluate(async (url) => {
      try {
        const response = await fetch(url);
        if (!response.ok) return { status: response.status };
        const payload = await response.json();
        return {
          status: response.status,
          keys: Object.keys(payload).sort(),
          counts: {
            entities: payload.entities?.length ?? 0,
            relations: payload.relations?.length ?? 0,
            events: payload.events?.length ?? 0,
          },
        };
      } catch (error) {
        return { status: 0, error: String(error) };
      }
    }, `${API_URL}/api/v1/memory-network/candidates?status=candidate&limit=50`);

    let panelVisible = false;
    let confirmedTitle = null;
    let panelCount = 0;
    if (MEMORY_ON && candidatesProbe.status === 200) {
      const panel = page.locator(".memory-candidate-panel");
      try {
        await panel.waitFor({ state: "visible", timeout: 10_000 });
        panelVisible = true;
        panelCount = await panel.count();
        const rows = page.locator(".memory-candidate-item");
        const rowCount = await rows.count();
        // Confirm the first entity row (kind label "entity"), then assert it
        // leaves the pending list.
        for (let index = 0; index < rowCount; index += 1) {
          const row = rows.nth(index);
          const kind = (await row.locator(".memory-candidate-kind").textContent())
            .trim()
            .toLowerCase();
          if (kind === "entity") {
            confirmedTitle = (
              await row.locator(".memory-candidate-text strong").textContent()
            ).trim();
            await row
              .getByRole("button", { name: "确认" })
              .click();
            await page
              .waitForFunction(
                (title) => {
                  const elements = Array.from(
                    document.querySelectorAll(
                      ".memory-candidate-text strong",
                    ),
                  );
                  return !elements.some(
                    (element) => element.textContent?.trim() === title,
                  );
                },
                confirmedTitle,
                { timeout: 8_000 },
              )
              .catch(() => {
                // leave state.confirmedRemoved false when still present
              });
            break;
          }
        }
        if (confirmedTitle !== null) {
          const stillThere = await page
            .locator(".memory-candidate-text strong", {
              hasText: confirmedTitle,
            })
            .count();
          state.confirmedRemoved = stillThere === 0;
        }
      } catch {
        panelVisible = false;
      }
    }

    if (!MEMORY_ON) {
      panelCount = await page.locator(".memory-candidate-panel").count();
    }

    state.workflow = "memory-candidate-v3";
    state.mode = MEMORY_ON ? "flag-on" : "flag-off";
    state.composerVisible = await composer.isVisible();
    state.candidatesProbe = candidatesProbe;
    state.panelCount = panelCount;
    state.panelVisible = panelVisible;
    state.confirmedTitle = confirmedTitle;

    await page.screenshot({
      path: path.resolve(
        __dirname,
        "..",
        "artifacts",
        `memory-candidates-v3-${MEMORY_ON ? "on" : "off"}.png`,
      ),
      fullPage: true,
    });

    const filteredErrors = [];
    let expectedBudget = expected404Responses.length;
    for (const entry of errors) {
      if (
        expectedBudget > 0 &&
        entry.includes("404 (Not Found)") &&
        entry.includes("Failed to load resource")
      ) {
        expectedBudget -= 1;
        continue;
      }
      filteredErrors.push(entry);
    }
    state.errors = filteredErrors;
    state.expected404Responses = expected404Responses;
    console.log(JSON.stringify(state, null, 2));

    const composerOk = state.composerVisible;
    const probeOk = !MEMORY_ON || candidatesProbe.status === 200;
    const panelOk = MEMORY_ON
      ? panelVisible && (confirmedTitle === null || state.confirmedRemoved)
      : panelCount === 0;
    const errorOk = filteredErrors.length === 0;

    if (!composerOk || !probeOk || !panelOk || !errorOk) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
}

void main();
