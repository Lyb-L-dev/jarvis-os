const { chromium } = require("../apps/web/node_modules/playwright");

function localDateTime(minutesFromNow) {
  const value = new Date(Date.now() + minutesFromNow * 60 * 1000);
  const shifted = new Date(
    value.getTime() - value.getTimezoneOffset() * 60_000,
  );
  return shifted.toISOString().slice(0, 16);
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.JARVIS_EDGE_PATH ??
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1050 },
    });
    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });
    page.on("pageerror", (error) => consoleErrors.push(error.message));

    await page.goto("http://127.0.0.1:3000/notifications", {
      waitUntil: "networkidle",
    });
    await page.getByText("Windows 后台在线").waitFor({ timeout: 15_000 });
    await page.screenshot({
      path: "E:\\贾维斯\\artifacts\\reminder-center-online.png",
      fullPage: true,
    });

    const form = page.locator(".reminder-form");
    await form.getByLabel("标题").fill("提醒延迟忽略验证");
    await form
      .getByLabel("播报内容")
      .fill("验证提醒的延迟、忽略和历史记录。");
    await form.getByLabel("提醒时间").fill(localDateTime(20));
    await form.getByLabel("自动语音播报").uncheck();
    await form.getByRole("button", { name: "安排提醒" }).click();
    await page
      .getByText("提醒已安排，关闭浏览器后仍会生效。")
      .waitFor();

    let futureCard = page
      .locator(".reminder-item")
      .filter({ hasText: "提醒延迟忽略验证" });
    await futureCard.getByRole("button", { name: "+10m" }).click();
    await page.getByText("已延迟 10 分钟。").waitFor();
    futureCard = page
      .locator(".reminder-item")
      .filter({ hasText: "提醒延迟忽略验证" });
    await futureCard.getByRole("button", { name: "忽略" }).click();
    await page.getByText("提醒已忽略。").waitFor();

    await form.getByLabel("标题").fill("Jarvis 桌面通知验证");
    await form
      .getByLabel("播报内容")
      .fill("这是一条仅用于验收的桌面通知。");
    await form.getByLabel("提醒时间").fill(localDateTime(-1));
    await form.getByLabel("自动语音播报").uncheck();
    await form.getByRole("button", { name: "安排提醒" }).click();
    await page
      .getByText("提醒已安排，关闭浏览器后仍会生效。")
      .waitFor();

    const deliveredCard = page
      .locator(".reminder-item")
      .filter({ hasText: "Jarvis 桌面通知验证" });
    await deliveredCard.getByText("已送达").waitFor({ timeout: 35_000 });
    await deliveredCard.getByText("桌面成功").waitFor({ timeout: 5_000 });
    await page.screenshot({
      path: "E:\\贾维斯\\artifacts\\reminder-delivery-history-verified.png",
      fullPage: true,
    });

    const ignoredCard = page
      .locator(".reminder-item")
      .filter({ hasText: "提醒延迟忽略验证" });
    await ignoredCard.getByRole("button", { name: "删除记录" }).click();
    await page.getByText("提醒记录已删除。").waitFor();
    const deliveredCardAfter = page
      .locator(".reminder-item")
      .filter({ hasText: "Jarvis 桌面通知验证" });
    await deliveredCardAfter
      .getByRole("button", { name: "删除记录" })
      .click();
    await page.getByText("提醒记录已删除。").waitFor();

    console.log(
      JSON.stringify({
        heading: await page
          .getByRole("heading", { name: "主动提醒" })
          .isVisible(),
        companionOnline: await page.getByText("Windows 后台在线").isVisible(),
        cleanupComplete:
          (await page.getByText("Jarvis 桌面通知验证").count()) === 0,
        consoleErrors,
      }),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
