const { chromium } = require("../apps/web/node_modules/playwright");
const path = require("node:path");

const baseUrl = "http://127.0.0.1:3000";
const candidateText = "请记住，我喜欢在回答开头先看到结论。";
const editedText = "我喜欢在回答开头先看到结论和关键依据。";

async function handleNextDialog(page, action, expectedText) {
  return new Promise((resolve, reject) => {
    page.once("dialog", async (dialog) => {
      try {
        if (!dialog.message().includes(expectedText)) {
          throw new Error(`Unexpected dialog: ${dialog.message()}`);
        }
        if (action === "accept") {
          await dialog.accept();
        } else {
          await dialog.dismiss();
        }
        resolve(dialog.message());
      } catch (error) {
        reject(error);
      }
    });
  });
}

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const screenshotPath = path.join(
    projectRoot,
    "artifacts",
    "memory-center-paid-confirmation-verified.png",
  );
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];
  const badResponses = [];

  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on("console", (message) => {
      if (message.type() === "error" || message.type() === "warning") {
        consoleMessages.push(`${message.type()}: ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("requestfailed", (request) => {
      if (request.failure()?.errorText === "net::ERR_ABORTED") {
        return;
      }
      failedRequests.push(
        `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
      );
    });
    page.on("response", (response) => {
      if (response.status() >= 400) {
        badResponses.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto(`${baseUrl}/chat`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    const conversationCount = await page.locator(".conversation-item").count();
    // Sprint 4 ruling: the chat "new conversation" button text is "新的对话"
    // (the acceptance script was stale). Keep a fallback for older builds.
    const newConversation = page
      .getByRole("button", { name: "新的对话" })
      .or(page.getByRole("button", { name: "新建对话" }));
    await newConversation.first().click();
    await page.waitForFunction(
      (count) => document.querySelectorAll(".conversation-item").length > count,
      conversationCount,
      { timeout: 10_000 },
    );
    await page.getByLabel("模型模式").selectOption("local");
    await page.getByLabel("发送给 Jarvis").fill(candidateText);
    await page.waitForFunction(
      () => {
        const button = document.querySelector('button[aria-label="发送"]');
        return button instanceof HTMLButtonElement && !button.disabled;
      },
      null,
      { timeout: 10_000 },
    );
    await page.getByRole("button", { name: "发送" }).click();
    await page.getByRole("button", { name: "停止生成" }).waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "发送" }).waitFor({
      state: "visible",
      timeout: 180_000,
    });
    await page.locator(".memory-notice").waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await page.getByRole("link", { name: "打开记忆中心" }).click();
    await page.waitForURL("**/memory");

    let card = page.locator(".memory-card").filter({ hasText: candidateText });
    await card.waitFor({ state: "visible", timeout: 15_000 });
    await card.getByRole("button", { name: "✓ 确认使用" }).click();
    await card.getByText("使用中", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await card.getByRole("button", { name: "编辑" }).click();
    await card.getByLabel("编辑记忆内容").fill(editedText);
    await page.getByRole("button", { name: "保存修改" }).click();
    card = page.locator(".memory-card").filter({ hasText: editedText });
    await card.waitFor({ state: "visible", timeout: 10_000 });

    await page.goto(`${baseUrl}/chat`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    await page.getByLabel("模型模式").selectOption("deep");
    const paidPrompt = "只回复“付费确认测试通过”，不要添加其他内容。";
    await page.getByLabel("发送给 Jarvis").fill(paidPrompt);
    const beforeDismiss = await page.locator(".message-row").count();
    const dismissed = handleNextDialog(page, "dismiss", "按量付费的 DeepSeek");
    await page.getByRole("button", { name: "发送" }).click();
    await dismissed;
    await page.waitForTimeout(300);
    const afterDismiss = await page.locator(".message-row").count();
    if (afterDismiss !== beforeDismiss) {
      throw new Error("Dismissing the paid-call dialog still created a message.");
    }

    await page.goto(`${baseUrl}/memory`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    card = page.locator(".memory-card").filter({ hasText: editedText });
    await card.waitFor({ state: "visible", timeout: 15_000 });
    await page.screenshot({ path: screenshotPath, fullPage: true });

    const deleting = handleNextDialog(page, "accept", "确定删除这条长期记忆");
    await card.getByRole("button", { name: "删除" }).click();
    await deleting;
    await card.waitFor({ state: "detached", timeout: 10_000 });

    await page.goto(`${baseUrl}/chat`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    const beforeArchive = await page.locator(".conversation-item").count();
    const archiving = handleNextDialog(page, "accept", "归档这个对话");
    await page.getByRole("button", { name: "归档" }).click();
    await archiving;
    await page.waitForFunction(
      (count) => document.querySelectorAll(".conversation-item").length < count,
      beforeArchive,
      { timeout: 10_000 },
    );

    const result = {
      memoryCandidateConfirmed: true,
      memoryEdited: true,
      paidDialogDismissedWithoutMessage: afterDismiss === beforeDismiss,
      paidCallNotMade: true,
      cleanupCompleted: true,
      consoleMessages,
      pageErrors,
      failedRequests,
      badResponses,
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
