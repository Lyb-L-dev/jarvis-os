const { chromium } = require("../apps/web/node_modules/playwright");
const path = require("node:path");

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const screenshotPath = path.join(projectRoot, "artifacts", "chat-page-verified.png");
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const consoleMessages = [];
    const pageErrors = [];
    const failedRequests = [];
    const notableResponses = [];

    page.on("console", (message) => {
      if (message.type() === "error" || message.type() === "warning") {
        consoleMessages.push(`${message.type()}: ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("requestfailed", (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
      );
    });
    page.on("response", (response) => {
      if (response.status() >= 400 || response.url().includes(":8000")) {
        notableResponses.push(`${response.status()} ${response.url()}`);
      }
    });

    const response = await page.goto("http://127.0.0.1:3000/chat", {
      waitUntil: "domcontentloaded",
      timeout: 15_000,
    });
    await page.waitForTimeout(5_000);
    const apiProbe = await page.evaluate(async () => {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/v1/chat/conversations",
        );
        return { status: response.status, body: await response.json() };
      } catch (error) {
        return { error: String(error) };
      }
    });
    const privacyToggle = page.locator(".privacy-toggle");
    const activeBeforeClick = await privacyToggle.evaluate((element) =>
      element.classList.contains("active"),
    );
    await privacyToggle.click();
    await page.waitForTimeout(300);
    const activeAfterClick = await privacyToggle.evaluate((element) =>
      element.classList.contains("active"),
    );
    if (activeAfterClick) {
      await privacyToggle.click();
      await page.waitForTimeout(150);
    }
    await page.screenshot({ path: screenshotPath, fullPage: true });

    const result = {
      status: response?.status(),
      title: await page.title(),
      conversations: await page.locator(".conversation-item").count(),
      messages: await page.locator(".message-row").count(),
      loadingVisible: await page.locator(".chat-loading").count(),
      hydrationInteractive: !activeBeforeClick && activeAfterClick,
      apiProbe,
      errorText: await page.locator(".chat-error").allTextContents(),
      consoleMessages,
      pageErrors,
      failedRequests,
      notableResponses,
      screenshotPath,
    };
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
