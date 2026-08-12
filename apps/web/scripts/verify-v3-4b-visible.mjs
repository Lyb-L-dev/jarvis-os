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
  let panelDeepLinks = null;
  let rollbackSidebar = null;

  if (expectedState === "enabled") {
    const expectedPanelDeepLinks = {
      CareerRadar: "/career",
      长期记忆: "/memory",
      本地知识: "/knowledge",
      成长计划: "/growth",
      任务编排: "/observatory",
      审批中心: "/approvals",
    };
    panelDeepLinks = {};
    for (const [title, expectedHref] of Object.entries(expectedPanelDeepLinks)) {
      const side = ["CareerRadar", "长期记忆", "本地知识"].includes(title)
        ? "资料与上下文"
        : "行动与结果";
      await page
        .getByRole("button", { name: `打开${side}面板选择器` })
        .click();
      await page.locator("button").filter({ hasText: title }).last().click();
      const deck = page.locator(
        `[data-workspace-deck][data-side="${side === "资料与上下文" ? "left" : "right"}"]`,
      );
      const actualHref = await deck
        .getByRole("link", { name: "打开完整页面" })
        .getAttribute("href");
      panelDeepLinks[title] = actualHref;
      if (actualHref !== expectedHref) {
        throw new Error(
          `${title} deep link mismatch: expected ${expectedHref}, received ${actualHref}.`,
        );
      }
    }
  }

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
    panelDeepLinks,
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
