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
    const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
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
    const center = page.locator(".approval-shell");
    await center.waitFor({ state: "visible", timeout: 20_000 });
    await center.getByText("等待你的决定").first().waitFor({ timeout: 20_000 });
    const result = {
      heading: await page.locator("h1").innerText(),
      humanControl: await page.getByText("HUMAN IN CONTROL").isVisible(),
      pendingPreview: await center.getByText("PREVIEW · NOT EXECUTED").isVisible(),
      r3Boundary: await center.getByText("永久禁用").first().isVisible(),
      blockedActions: await center.locator(".approval-permanent-blocks span").count(),
      approvalButtons: await center.getByRole("button", { name: "批准范围" }).count(),
      executeButtons: await center
        .getByRole("button", { name: "执行已批准动作" })
        .count(),
      errors,
      failedRequests,
    };
    await page.screenshot({
      path: path.resolve(
        __dirname,
        "..",
        "artifacts",
        "approval-center-sprint29.png",
      ),
      fullPage: true,
    });
    console.log(JSON.stringify(result, null, 2));
    if (
      !result.humanControl ||
      !result.pendingPreview ||
      !result.r3Boundary ||
      result.blockedActions !== 4 ||
      result.approvalButtons !== 1 ||
      result.executeButtons !== 0 ||
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
