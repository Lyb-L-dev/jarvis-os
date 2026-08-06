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

    await page.goto("http://127.0.0.1:3000/intelligence", {
      waitUntil: "networkidle",
    });
    const panel = page.locator(".research-workflow");
    await panel.waitFor({ state: "visible", timeout: 15_000 });
    const createForm = page.locator(".research-create");
    const question = page.getByLabel("你想研究什么？");
    const modelChoices = page.locator(".research-workflow .workflow-model-choice button");
    const sourcePicker = page.locator(".research-source-picker");
    const state = {
      heading: await panel.locator("h2").first().innerText(),
      createVisible: await createForm.isVisible().catch(() => false),
      questionVisible: await question.isVisible().catch(() => false),
      modelChoiceCount: await modelChoices.count(),
      sourcePickerVisible: await sourcePicker.isVisible().catch(() => false),
      feedback: await page.locator(".growth-feedback").allInnerTexts(),
      errors,
      failedRequests,
    };
    await page.screenshot({
      path: path.resolve(__dirname, "..", "artifacts", "research-workflow-sprint26.png"),
      fullPage: true,
    });
    console.log(JSON.stringify(state, null, 2));
    if (
      state.heading !== "Research Agent" ||
      !state.createVisible ||
      !state.questionVisible ||
      state.modelChoiceCount !== 4 ||
      !state.sourcePickerVisible ||
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
