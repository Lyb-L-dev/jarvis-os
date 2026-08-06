const { chromium } = require("../apps/web/node_modules/playwright");
const path = require("node:path");

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
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("requestfailed", (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
      );
    });

    await page.goto("http://127.0.0.1:3000/growth", {
      waitUntil: "networkidle",
    });
    const panel = page.locator(".growth-workflow");
    await panel.waitFor({ state: "visible", timeout: 15_000 });
    const createForm = page.locator(".growth-workflow-create");
    const objective = page.getByLabel("你想实现什么目标？");
    const state = {
      panelText: await panel.innerText(),
      createCount: await createForm.count(),
      createVisible: await createForm.isVisible().catch(() => false),
      objectiveCount: await objective.count(),
      objectiveVisible: await objective.isVisible().catch(() => false),
      feedback: await page.locator(".growth-feedback").allInnerTexts(),
      errors,
      failedRequests,
    };
    await page.screenshot({
      path: path.resolve(__dirname, "..", "artifacts", "growth-workflow-sprint25.png"),
      fullPage: true,
    });
    console.log(JSON.stringify(state, null, 2));
    if (!state.createVisible || !state.objectiveVisible || errors.length) {
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
