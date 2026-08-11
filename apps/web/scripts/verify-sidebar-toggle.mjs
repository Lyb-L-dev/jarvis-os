import { chromium } from "playwright";

const baseUrl = process.env.JARVIS_WEB_BASE_URL || "http://127.0.0.1:3000";
const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({ viewport: { width: 1720, height: 1000 } });
const page = await context.newPage();

try {
  await page.goto(`${baseUrl}/chat`, { waitUntil: "networkidle" });
  await page.evaluate(() => {
    window.localStorage.setItem("jarvis:sidebar-hidden:v1", "false");
  });
  await page.reload({ waitUntil: "networkidle" });

  const visibleMain = await page.locator("main").boundingBox();
  await page.getByRole("button", { name: "隐藏侧边栏" }).click();
  const hiddenMain = await page.locator("main").boundingBox();
  const hiddenSidebarCount = await page.locator("#jarvis-sidebar").count();

  await page.reload({ waitUntil: "networkidle" });
  const persisted = await page
    .getByRole("button", { name: "显示侧边栏" })
    .isVisible();

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.evaluate(() => {
    window.localStorage.setItem("jarvis:sidebar-hidden:v1", "false");
    window.dispatchEvent(new Event("jarvis:sidebar-change"));
  });
  const laptopSidebarVisible = await page.locator("#jarvis-sidebar").isVisible();
  const laptopToggleVisible = await page.locator(".sidebar-toggle").isVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  const mobileSidebarVisible = await page.locator("#jarvis-sidebar").isVisible();
  const mobileToggleVisible = await page.locator(".sidebar-toggle").isVisible();

  const result = {
    visibleMainX: visibleMain?.x,
    hiddenMainX: hiddenMain?.x,
    hiddenSidebarCount,
    persisted,
    laptopSidebarVisible,
    laptopToggleVisible,
    mobileSidebarVisible,
    mobileToggleVisible,
  };
  console.log(JSON.stringify(result));

  if (
    !visibleMain ||
    !hiddenMain ||
    visibleMain.x < 300 ||
    hiddenMain.x !== 0 ||
    hiddenSidebarCount !== 0 ||
    !persisted ||
    laptopSidebarVisible ||
    laptopToggleVisible ||
    mobileSidebarVisible ||
    mobileToggleVisible
  ) {
    throw new Error("Sidebar visibility behavior did not match the layout contract.");
  }
} finally {
  await browser.close();
}
