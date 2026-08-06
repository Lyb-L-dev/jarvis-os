// Sprint 4 visual regression baseline capture (QA & Reliability).
// Usage: node scripts/verify_visual_baseline.cjs [--seed-only|--capture-only]
// Requires: backend on 127.0.0.1:8000 (SQLite dev override) + frontend on
// 127.0.0.1:3000. Writes PNGs + manifest to evals/visual-baselines/.
const { chromium } = require("../apps/web/node_modules/playwright");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const BASE_URL = "http://127.0.0.1:3000";
const API_URL = "http://127.0.0.1:8000/api/v1";
const OUT_DIR = path.join(__dirname, "..", "evals", "visual-baselines");
const INVEST_DIR = path.join(OUT_DIR, "investment");
const ENGLISH_DIR = path.join(OUT_DIR, "english");
const CHAT_DIR = path.join(OUT_DIR, "chat");
const GROWTH_DIR = path.join(OUT_DIR, "growth");

const manifest = {
  created_at: new Date().toISOString(),
  base_url: BASE_URL,
  api_url: API_URL,
  viewport: "1440x900",
  entries: [],
};

async function api(method, urlPath, body) {
  const response = await fetch(`${API_URL}${urlPath}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    throw new Error(`${method} ${urlPath} -> ${response.status}: ${text.slice(0, 300)}`);
  }
  return payload;
}

async function seedInvestmentData() {
  const assets = [];
  const definitions = [
    { name: "苹果", symbol: "AAPL", market: "NASDAQ", asset_type: "stock", currency: "USD", latest_price: 190 },
    { name: "比特币", symbol: "BTC-USD", market: "CRYPTO", asset_type: "crypto", currency: "USD", latest_price: 60000 },
    { name: "特斯拉", symbol: "TSLA", market: "NASDAQ", asset_type: "stock", currency: "USD", latest_price: null },
    { name: "贵州茅台", symbol: "600519", market: "SSE", asset_type: "stock", currency: "CNY", latest_price: 1700 },
    { name: "未建仓观察", symbol: "OBSV", market: "NYSE", asset_type: "etf", currency: "USD", latest_price: 12 },
  ];
  for (const definition of definitions) {
    assets.push(await api("POST", "/investment/assets", definition));
  }
  const bySymbol = Object.fromEntries(assets.map((asset) => [asset.symbol, asset]));

  await api("POST", "/investment/positions", {
    asset_id: bySymbol["AAPL"].id,
    quantity: 100,
    average_cost: 150,
    fees: 5,
    transaction_date: "2026-06-01",
    reason: "长线持有苹果，看好AI服务收入",
    target_allocation: 30,
    risk_level: "medium",
  });
  await api("POST", "/investment/positions", {
    asset_id: bySymbol["BTC-USD"].id,
    quantity: 0.5,
    average_cost: 70000,
    fees: 3,
    transaction_date: "2026-05-10",
    reason: "分批建仓比特币",
    target_allocation: 20,
    risk_level: "high",
  });
  await api("POST", "/investment/positions", {
    asset_id: bySymbol["TSLA"].id,
    quantity: 10,
    average_cost: 250,
    fees: 2,
    transaction_date: "2026-06-20",
    reason: "电动车渗透率跟踪",
    target_allocation: 10,
    risk_level: "very_high",
  });
  await api("POST", "/investment/positions", {
    asset_id: bySymbol["600519"].id,
    quantity: 200,
    average_cost: 1500,
    fees: 8,
    transaction_date: "2026-04-15",
    reason: "消费龙头稳健配置",
    target_allocation: 40,
    risk_level: "low",
  });

  await api("POST", "/investment/transactions", {
    asset_id: bySymbol["AAPL"].id,
    transaction_type: "sell",
    transaction_date: "2026-07-01",
    quantity: 10,
    unit_price: 195,
    fees: 1,
    reason: "部分止盈",
  });
  await api("POST", "/investment/transactions", {
    asset_id: bySymbol["AAPL"].id,
    transaction_type: "dividend",
    transaction_date: "2026-07-05",
    cash_amount: 25,
    reason: "季度分红",
  });

  await api("POST", "/investment/theses", {
    asset_id: bySymbol["AAPL"].id,
    title: "苹果长期投资理由（当前版）",
    original_reason: "生态粘性 + AI服务货币化",
    current_view: "维持看好",
    key_assumptions: ["服务收入占比提升", "硬件周期平稳"],
    watch_events: ["财报指引", "AI新品发布"],
    invalidation_conditions: ["生态竞争力显著下滑"],
    risk_level: "medium",
    cloud_allowed: true,
  });
  await api("POST", "/investment/theses", {
    asset_id: bySymbol["AAPL"].id,
    title: "苹果早期版本（历史）",
    original_reason: "初版调研结论",
    current_view: null,
    key_assumptions: [],
    watch_events: [],
    invalidation_conditions: [],
    risk_level: "medium",
    cloud_allowed: false,
  });
  await api("POST", "/investment/theses", {
    asset_id: bySymbol["BTC-USD"].id,
    title: "比特币阶段性配置",
    original_reason: "数字黄金叙事",
    current_view: "已失效",
    key_assumptions: ["监管明朗"],
    watch_events: [],
    invalidation_conditions: ["监管收紧"],
    risk_level: "high",
    cloud_allowed: false,
  });

  const review = await api("POST", "/investment/reviews/generate", {
    asset_id: bySymbol["AAPL"].id,
    review_type: "weekly",
    period_start: "2026-07-27",
    period_end: "2026-08-02",
  });
  await api("PATCH", `/investment/reviews/${review.id}`, {
    status: "confirmed",
    summary: "本周苹果走势符合预期，维持持仓。",
  });
  await api("POST", "/investment/reviews/generate", {
    asset_id: bySymbol["BTC-USD"].id,
    review_type: "manual",
    period_start: "2026-07-27",
    period_end: "2026-08-02",
  });

  const candidates = await api(
    "GET",
    `/investment/assets/${bySymbol["AAPL"].id}/news?candidates=true&limit=50`,
  );
  const aaplNews = candidates.find((item) => item.title.includes("苹果"));
  if (aaplNews) {
    await api("POST", `/investment/assets/${bySymbol["AAPL"].id}/news/${aaplNews.id}`, {
      relationship_note: "财报发布后关联到苹果持仓",
    });
  }
  return { assets, newsItems: candidates };
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

async function capture(page, name, directory, label) {
  fs.mkdirSync(directory, { recursive: true });
  const filePath = path.join(directory, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: false });
  manifest.entries.push({
    file: path.relative(OUT_DIR, filePath),
    page: path.basename(directory),
    label,
    sha256: sha256(fs.readFileSync(filePath)),
  });
  console.log(`[shot] ${label} -> ${path.relative(OUT_DIR, filePath)}`);
}

async function goto(page, urlPath) {
  const response = await page.goto(`${BASE_URL}${urlPath}`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(1800);
  return response;
}

async function clickText(page, text, timeoutMs = 8000) {
  const locator = page.getByText(text, { exact: false }).first();
  await locator.waitFor({ state: "visible", timeout: timeoutMs });
  await locator.click();
}

async function tryClickText(page, text, timeoutMs = 4000) {
  try {
    await clickText(page, text, timeoutMs);
    return true;
  } catch {
    return false;
  }
}

async function tryClickButton(page, text, timeoutMs = 4000) {
  try {
    const locator = page.locator("button").filter({ hasText: text }).first();
    await locator.waitFor({ state: "visible", timeout: timeoutMs });
    await locator.click();
    return true;
  } catch {
    return false;
  }
}

async function captureInvestment(page) {
  await goto(page, "/investment");
  await capture(page, "01-loading-or-initial", INVEST_DIR, "1. 加载屏/初始态（尽力）");

  await tryClickText(page, "持仓");
  await page.waitForTimeout(600);
  await capture(page, "16a-tab-positions", INVEST_DIR, "16. Tab-持仓");
  await tryClickText(page, "交易");
  await page.waitForTimeout(600);
  await capture(page, "16b-tab-transactions", INVEST_DIR, "16. Tab-交易");
  await tryClickText(page, "投资理由");
  await page.waitForTimeout(600);
  await capture(page, "16c-tab-theses", INVEST_DIR, "16. Tab-理由");
  await tryClickText(page, "关联情报");
  await page.waitForTimeout(600);
  await capture(page, "16d-tab-news", INVEST_DIR, "16. Tab-新闻");
  await tryClickText(page, "复盘");
  await page.waitForTimeout(600);
  await capture(page, "16e-tab-reviews", INVEST_DIR, "16. Tab-复盘");

  await tryClickText(page, "持仓");
  await page.waitForTimeout(400);
  if (await tryClickButton(page, "编辑 / 更新价格")) {
    await page.waitForTimeout(500);
    await capture(page, "06-asset-form-edit", INVEST_DIR, "6. 资产表单-编辑（币种禁用）");
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  }
  if (await tryClickText(page, "添加资产")) {
    await page.waitForTimeout(500);
    await capture(page, "05-asset-form-new", INVEST_DIR, "5. 资产表单-新建（含初始持仓区）");
    await page.keyboard.press("Escape");
  }
  await page.waitForTimeout(300);
  if (await tryClickText(page, "记录交易")) {
    await page.waitForTimeout(500);
    await capture(page, "07-tx-form-buy", INVEST_DIR, "7. 交易表单-买入");
    try {
      const typeSelect = page.locator("select").first();
      await typeSelect.selectOption({ label: "分红" });
      await page.waitForTimeout(300);
      await capture(page, "07b-tx-form-dividend", INVEST_DIR, "7b. 交易表单-分红字段切换");
    } catch {
      // dividend toggle not available in this build
    }
    await page.keyboard.press("Escape");
  }
  await page.waitForTimeout(300);
  await tryClickButton(page, "投资理由");
  await page.waitForTimeout(400);
  if (
    (await tryClickButton(page, "记录新理由")) ||
    (await tryClickButton(page, "新建理由"))
  ) {
    await page.waitForTimeout(500);
    await capture(page, "09-thesis-form", INVEST_DIR, "9. 理由表单");
    await page.keyboard.press("Escape");
  }
}

async function captureEnglish(page) {
  await goto(page, "/english");
  await capture(page, "01-tab-practice", ENGLISH_DIR, "English-对话训练Tab");
  if (await tryClickButton(page, "错题本")) {
    await page.waitForTimeout(500);
    await capture(page, "02-tab-mistakes", ENGLISH_DIR, "English-错题本Tab");
  }
  if (await tryClickButton(page, "今日复习")) {
    await page.waitForTimeout(500);
    await capture(page, "03-tab-review", ENGLISH_DIR, "English-今日复习Tab");
  }
  if (await tryClickButton(page, "对话训练")) {
    await page.waitForTimeout(400);
    if (
      (await tryClickButton(page, "开始英语对话")) ||
      (await tryClickButton(page, "开始练习")) ||
      (await tryClickButton(page, "新练习"))
    ) {
      await page.waitForTimeout(500);
      await capture(page, "04-session-setup-form", ENGLISH_DIR, "English-会话设置表单");
      await page.keyboard.press("Escape");
    }
  }
}

async function captureChat(page) {
  await goto(page, "/chat");
  await capture(page, "01-workspace-empty", CHAT_DIR, "Chat-工作区（空态）");
  if (await tryClickButton(page, "新的对话")) {
    await page.waitForTimeout(500);
    await capture(page, "02-new-chat-form", CHAT_DIR, "Chat-新对话（表单态）");
  }
  await capture(page, "03-composer-state", CHAT_DIR, "Chat-输入区（Composer）");
}

async function captureGrowth(page) {
  await goto(page, "/growth");
  await capture(page, "01-tab-today-empty", GROWTH_DIR, "Growth-今日Tab（空态）");
  if (await tryClickText(page, "长期目标")) {
    await page.waitForTimeout(500);
    await capture(page, "02-tab-goals-empty", GROWTH_DIR, "Growth-目标Tab（空态）");
  }
  if (await tryClickText(page, "本周复盘")) {
    await page.waitForTimeout(500);
    await capture(page, "03-tab-review-empty", GROWTH_DIR, "Growth-复盘Tab（空态）");
  }
  if (await tryClickText(page, "今日行动")) {
    await page.waitForTimeout(400);
    if (await tryClickText(page, "新建任务")) {
      await page.waitForTimeout(500);
      await capture(page, "04-task-form", GROWTH_DIR, "Growth-任务表单");
      await page.keyboard.press("Escape");
    }
  }
}

async function main() {
  const args = process.argv.slice(2);
  const seedOnly = args.includes("--seed-only");
  const captureOnly = args.includes("--capture-only");

  if (!captureOnly) {
    console.log("[seed] creating investment demo data...");
    const seeded = await seedInvestmentData();
    console.log(`[seed] ok (${seeded.assets.length} assets)`);
  }
  if (seedOnly) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(OUT_DIR, "manifest.json"),
      JSON.stringify(manifest, null, 2),
    );
    return;
  }

  let browser = null;
  let page = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      browser = await chromium.launch({ channel: "msedge", headless: true });
      page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      break;
    } catch (error) {
      console.warn(`[launch] attempt ${attempt} failed: ${error.message}`);
      if (browser) {
        try {
          await browser.close();
        } catch {
          // ignore close failures during retry
        }
      }
      await new Promise((resolve) => setTimeout(resolve, 1500 * attempt));
    }
  }
  if (!browser || !page) {
    throw new Error("Edge could not be launched after 3 attempts");
  }
  try {
    await captureInvestment(page);
    await captureEnglish(page);
    await captureChat(page);
    await captureGrowth(page);
  } finally {
    await browser.close();
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(OUT_DIR, "manifest.json"),
    JSON.stringify(manifest, null, 2),
  );
  console.log(`[done] ${manifest.entries.length} screenshots -> evals/visual-baselines/`);
}

main().catch((error) => {
  console.error("ERR:", error.message);
  process.exit(1);
});
