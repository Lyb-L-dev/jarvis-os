import { chromium } from "playwright";

const baseUrl = process.env.JARVIS_WEB_BASE_URL || "http://127.0.0.1:3000";
const apiUrl = process.env.JARVIS_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const cases = [
  { name: "career-cn", prompt: "帮我准备下一轮岗位面试", expected: ["career"] },
  { name: "career-en", prompt: "Compare these offer options", expected: ["career"] },
  { name: "memory", prompt: "请从长期记忆里找我的偏好", expected: ["memory"] },
  { name: "knowledge", prompt: "搜索 Obsidian 里的本地资料", expected: ["knowledge"] },
  { name: "growth", prompt: "检查成长计划的里程碑", expected: ["growth"] },
  { name: "orchestrator-cn", prompt: "用多步骤工作流完成调研", expected: ["orchestrator"] },
  { name: "orchestrator-en", prompt: "Run a research workflow", expected: ["orchestrator"] },
  { name: "approval", prompt: "有哪些操作待确认审批", expected: ["approval"] },
  { name: "mixed", prompt: "结合岗位、长期记忆和成长计划安排面试", expected: ["career", "memory", "growth"] },
  { name: "negative-date", prompt: "What day of the week is today?", expected: [] },
  { name: "negative-company", prompt: "Explain how this system works", expected: [] },
  { name: "negative-offer-substring", prompt: "The coffer is made of wood", expected: [] },
  { name: "negative-researcher", prompt: "Describe a researcher profile", expected: [] },
];

function sorted(values) {
  return [...values].sort();
}

function equalPanelSets(actual, expected) {
  return JSON.stringify(sorted(actual)) === JSON.stringify(sorted(expected));
}

const browser = await chromium.launch({ channel: "msedge", headless: true });
const createdConversationIds = [];

try {
  const results = [];
  for (const testCase of cases) {
    const context = await browser.newContext({
      viewport: { width: 1720, height: 1000 },
    });
    const createResponse = await context.request.post(`${apiUrl}/chat/conversations`, {
      data: { model_mode: "standard", title: `V3-4b intent gate: ${testCase.name}` },
    });
    if (!createResponse.ok()) {
      throw new Error(`Unable to create isolated conversation: ${createResponse.status()}.`);
    }
    const conversation = await createResponse.json();
    createdConversationIds.push(conversation.id);

    await context.addInitScript(() => {
      window.localStorage.removeItem("jarvis:twin-workspace:v2");
    });
    const page = await context.newPage();
    await page.route("**/chat/conversations/*/stream", (route) => route.abort());
    await page.goto(`${baseUrl}/chat`, { waitUntil: "domcontentloaded" });
    await page.locator('textarea[aria-label="发送给 Jarvis"]').waitFor({
      state: "visible",
      timeout: 30_000,
    });
    const contract = await page
      .locator('[data-design-contract="jarvis-chat-twin-v3-4b"]')
      .count();
    if (contract !== 1) {
      throw new Error("V3-4b intent verification requires the convergence Flag enabled.");
    }
    await page.waitForFunction(
      (title) => document.querySelector(".workspace-title strong")?.textContent === title,
      `V3-4b intent gate: ${testCase.name}`,
      { timeout: 10_000 },
    );
    const activeTitle = await page.locator(".workspace-title strong").textContent();
    if (activeTitle !== `V3-4b intent gate: ${testCase.name}`) {
      throw new Error(`Isolated conversation did not become active: ${activeTitle}.`);
    }
    await page.locator('textarea[aria-label="发送给 Jarvis"]').fill(testCase.prompt);
    await page.locator('textarea[aria-label="发送给 Jarvis"]').press("Enter");
    await page.waitForFunction(
      () => {
        const raw = window.localStorage.getItem("jarvis:twin-workspace:v2");
        return raw !== null;
      },
      null,
      { timeout: 5_000 },
    );

    const state = await page.evaluate(() =>
      JSON.parse(window.localStorage.getItem("jarvis:twin-workspace:v2") || "{}"),
    );
    const actual = [...(state.left || []), ...(state.right || [])];
    results.push({
      name: testCase.name,
      expected: testCase.expected,
      actual,
      passed: equalPanelSets(actual, testCase.expected),
    });
    await context.request
      .post(`${apiUrl}/chat/conversations/${conversation.id}/archive`)
      .catch(() => null);
    await context.close();
  }

  console.log(JSON.stringify({ cases: results.length, results }, null, 2));
  const failed = results.filter((result) => !result.passed);
  if (failed.length > 0) {
    throw new Error(`V3-4b intent matrix failed: ${failed.map((item) => item.name).join(", ")}.`);
  }
} finally {
  for (const conversationId of createdConversationIds) {
    await fetch(`${apiUrl}/chat/conversations/${conversationId}/archive`, {
      method: "POST",
    }).catch(() => null);
  }
  if (browser.isConnected()) {
    await browser.close();
  }
}
