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
    const page = await browser.newPage({ viewport: { width: 1500, height: 1250 } });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("requestfailed", (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
      );
    });

    await page.goto("http://127.0.0.1:3000/approvals", {
      waitUntil: "networkidle",
    });
    const panel = page.locator(".automation-provider-panel");
    await panel.waitFor({ state: "visible", timeout: 20_000 });
    await panel.getByText("运行正常").waitFor({ timeout: 20_000 });

    const calendarButton = panel.getByRole("button", { name: /读取沙盒日历/ });
    await calendarButton.click();
    await page.getByText("只读日历测试完成，没有修改任何外部数据。").waitFor();
    const calendarReadOnly = await panel.locator("pre").getByText(/"read_only": true/).isVisible();

    const emailButton = panel.getByRole("button", { name: /生成本地邮件草稿/ });
    await emailButton.click();
    await page.getByText("本地邮件草稿已生成，没有发送邮件。").waitFor();
    const emailNotSent = await panel.locator("pre").getByText(/"not_sent": true/).isVisible();

    const result = {
      providerReady: await panel.getByText("运行正常").isVisible(),
      isolated: await panel.getByText("独立网络").isVisible(),
      signed: await panel.getByText("HMAC 签名").isVisible(),
      noRedis: await panel.getByText("未使用").isVisible(),
      noRealAccounts: await panel.getByText("未连接").isVisible(),
      noExternalWrites: await panel.getByText("已关闭").isVisible(),
      calendarReadOnly,
      emailNotSent,
      errors,
      failedRequests,
    };
    await page.screenshot({
      path: path.resolve(__dirname, "..", "artifacts", "n8n-provider-sprint30.png"),
      fullPage: true,
    });
    console.log(JSON.stringify(result, null, 2));
    if (
      !result.providerReady ||
      !result.isolated ||
      !result.signed ||
      !result.noRedis ||
      !result.noRealAccounts ||
      !result.noExternalWrites ||
      !result.calendarReadOnly ||
      !result.emailNotSent ||
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
