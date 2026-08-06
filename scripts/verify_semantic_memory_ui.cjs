const { chromium } = require("../apps/web/node_modules/playwright");
const path = require("node:path");

async function inspectPage(page, route, screenshotName) {
  await page.goto(`http://127.0.0.1:3000/${route}`, {
    waitUntil: "networkidle",
  });
  const panel = page.locator(".semantic-index-panel");
  await panel.waitFor({ state: "visible", timeout: 15_000 });
  await panel.getByText("语义检索就绪").waitFor({ timeout: 15_000 });
  const state = {
    route,
    heading: await panel.locator("h2").innerText(),
    coverageVisible: await panel.getByText("100.0%").isVisible(),
    readyVisible: await panel.getByText("语义检索就绪").isVisible(),
    rebuildEnabled: await panel.getByRole("button", { name: "重建语义索引" }).isEnabled(),
  };
  await page.screenshot({
    path: path.resolve(__dirname, "..", "artifacts", screenshotName),
    fullPage: true,
  });
  return state;
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.JARVIS_EDGE_PATH ??
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const errors = [];
  const failedRequests = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("requestfailed", (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
      );
    });

    const memory = await inspectPage(
      page,
      "memory",
      "semantic-memory-sprint27-memory.png",
    );
    const knowledge = await inspectPage(
      page,
      "knowledge",
      "semantic-memory-sprint27-knowledge.png",
    );
    const result = { memory, knowledge, errors, failedRequests };
    console.log(JSON.stringify(result, null, 2));
    if (
      !memory.coverageVisible ||
      !memory.readyVisible ||
      !memory.rebuildEnabled ||
      !knowledge.coverageVisible ||
      !knowledge.readyVisible ||
      !knowledge.rebuildEnabled ||
      errors.length ||
      failedRequests.length
    ) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
