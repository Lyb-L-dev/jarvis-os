import { chromium } from "playwright";

const baseUrl = process.env.JARVIS_WEB_BASE_URL || "http://127.0.0.1:3000";
const expectedState = process.argv
  .find((argument) => argument.startsWith("--expect="))
  ?.split("=", 2)[1];

if (!new Set(["enabled", "disabled"]).has(expectedState)) {
  throw new Error("Pass --expect=enabled or --expect=disabled.");
}

const browser = await chromium.launch({
  channel: "msedge",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1720, height: 1000 } });

try {
  await page.goto(`${baseUrl}/chat`, { waitUntil: "networkidle" });
  const contract = await page
    .locator('[data-design-contract="jarvis-chat-twin-v3-4b"]')
    .count();
  const decks = await page.locator("[data-workspace-deck]").count();
  const timeline = await page.locator("main.chat-page").count();
  let rollbackSidebar = null;

  if (expectedState === "disabled") {
    await page.evaluate(() => {
      window.localStorage.setItem("jarvis:sidebar-hidden:v1", "true");
    });
    await page.reload({ waitUntil: "networkidle" });
    rollbackSidebar = {
      sidebarCount: await page.locator("#jarvis-sidebar").count(),
      toggleCount: await page.locator(".sidebar-toggle").count(),
      shellState: await page.locator(".app-shell").getAttribute("data-sidebar-state"),
    };
  }

  console.log(JSON.stringify({
    url: page.url(),
    expectedState,
    contract,
    decks,
    timeline,
    rollbackSidebar,
  }));
  const valid = expectedState === "enabled"
    ? contract === 1 && decks === 2 && timeline === 0
    : contract === 0 &&
      decks === 0 &&
      timeline === 1 &&
      rollbackSidebar?.sidebarCount === 1 &&
      rollbackSidebar.toggleCount === 0 &&
      rollbackSidebar.shellState === "visible";
  if (!valid) {
    throw new Error(
      `V3-4b ${expectedState} path mismatch: contract=${contract}, decks=${decks}, timeline=${timeline}.`,
    );
  }
} finally {
  await browser.close();
}
