import { chromium } from "playwright";

const baseUrl = process.env.JARVIS_WEB_BASE_URL || "http://127.0.0.1:3000";
const apiUrl = process.env.JARVIS_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const storageKey = "jarvis:v3-4b:observation:v1";
const allowedKeys = new Set([
  "event_id",
  "occurred_at",
  "observation_session",
  "event_type",
  "viewport",
  "source",
  "panel_id",
  "panel_ids",
  "suppressed_panel_ids",
  "side",
  "left_count",
  "right_count",
  "target",
]);
const forbiddenKeys = new Set([
  "prompt",
  "content",
  "response",
  "conversation_id",
  "memory",
  "file",
]);

const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({
  acceptDownloads: true,
  viewport: { width: 1720, height: 1000 },
});
let conversationId = null;

try {
  const createResponse = await context.request.post(`${apiUrl}/chat/conversations`, {
    data: { model_mode: "standard", title: "V3-4b observation gate" },
  });
  if (!createResponse.ok()) {
    throw new Error(`Unable to create observation conversation: ${createResponse.status()}.`);
  }
  const conversation = await createResponse.json();
  conversationId = conversation.id;

  const page = await context.newPage();
  await page.route("**/chat/conversations/*/stream", (route) => route.abort());
  await page.goto(`${baseUrl}/chat`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    (title) => document.querySelector(".workspace-title strong")?.textContent === title,
    "V3-4b observation gate",
  );
  await page.evaluate((key) => window.localStorage.removeItem(key), storageKey);

  const prompt = "请结合岗位和成长计划给我建议";
  const composer = page.locator('textarea[aria-label="发送给 Jarvis"]');
  await composer.fill(prompt);
  await composer.press("Enter");
  await page.waitForFunction(
    (key) => {
      const raw = window.localStorage.getItem(key);
      if (!raw) return false;
      const events = JSON.parse(raw);
      return events.some(
        (event) =>
          event.event_type === "intent_evaluated" &&
          event.panel_ids?.includes("career") &&
          event.panel_ids?.includes("growth"),
      );
    },
    storageKey,
  );

  await page.getByRole("button", { name: "关闭CareerRadar" }).click();
  await composer.fill("继续查看岗位");
  await composer.press("Enter");
  await page.waitForFunction(
    (key) => {
      const events = JSON.parse(window.localStorage.getItem(key) || "[]");
      return events.some(
        (event) =>
          event.event_type === "intent_evaluated" &&
          event.suppressed_panel_ids?.includes("career"),
      );
    },
    storageKey,
  );
  await page
    .getByRole("button", { name: "打开资料与上下文面板选择器" })
    .click();
  await page.locator("button").filter({ hasText: "CareerRadar" }).last().click();

  await page
    .locator('[data-workspace-deck][data-side="left"]')
    .getByRole("link", { name: "打开完整页面" })
    .click();
  await page.waitForURL("**/career");
  await page.goto(`${baseUrl}/chat`, { waitUntil: "domcontentloaded" });

  const events = await page.evaluate((key) => {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : [];
  }, storageKey);
  const serialized = JSON.stringify(events);
  const unexpectedKeys = [
    ...new Set(events.flatMap((event) => Object.keys(event))),
  ].filter((key) => !allowedKeys.has(key));
  const forbiddenPresent = [...forbiddenKeys].filter(
    (key) => events.some((event) => Object.hasOwn(event, key)),
  );
  const eventTypes = [...new Set(events.map((event) => event.event_type))];
  const deepLinkRecorded = events.some(
    (event) =>
      event.event_type === "panel_deep_link" &&
      event.panel_id === "career" &&
      event.target === "/career",
  );
  const closeRecorded = events.some(
    (event) => event.event_type === "panel_closed" && event.panel_id === "career",
  );
  const suppressionRecorded = events.some(
    (event) =>
      event.event_type === "intent_evaluated" &&
      event.suppressed_panel_ids?.includes("career"),
  );
  const observationButton = page.getByRole("button", {
    name: "导出 V3-4b 灰度观察记录",
  });
  const downloadPromise = page.waitForEvent("download");
  await observationButton.click();
  const download = await downloadPromise;

  const result = {
    eventCount: events.length,
    eventTypes,
    deepLinkRecorded,
    closeRecorded,
    suppressionRecorded,
    unexpectedKeys,
    forbiddenPresent,
    containsPrompt: serialized.includes(prompt),
    downloadName: download.suggestedFilename(),
  };
  console.log(JSON.stringify(result, null, 2));

  if (
    events.length < 8 ||
    !eventTypes.includes("intent_evaluated") ||
    !eventTypes.includes("panel_opened") ||
    !eventTypes.includes("workspace_snapshot") ||
    !deepLinkRecorded ||
    !closeRecorded ||
    !suppressionRecorded ||
    unexpectedKeys.length > 0 ||
    forbiddenPresent.length > 0 ||
    result.containsPrompt ||
    !result.downloadName.startsWith("jarvis-v3-4b-observation-")
  ) {
    throw new Error("V3-4b observation ledger did not match its privacy contract.");
  }
} finally {
  if (conversationId) {
    await fetch(`${apiUrl}/chat/conversations/${conversationId}/archive`, {
      method: "POST",
    }).catch(() => null);
  }
  await context.close();
  await browser.close();
}
