const { chromium } = require("../apps/web/node_modules/playwright");
const path = require("node:path");

const baseUrl = "http://127.0.0.1:3000";
const apiUrl = "http://127.0.0.1:8000/api/v1";
const goalTitle = "[验收] 建立 AI 成长闭环";
const taskTitle = "[验收] 完成成长管理端到端测试";

async function acceptDialogs(page, answers) {
  let index = 0;
  return new Promise((resolve, reject) => {
    const handler = async (dialog) => {
      try {
        const answer = answers[index];
        if (answer === undefined) {
          throw new Error(`Unexpected dialog: ${dialog.message()}`);
        }
        index += 1;
        await dialog.accept(answer);
        if (index === answers.length) {
          page.off("dialog", handler);
          resolve();
        }
      } catch (error) {
        page.off("dialog", handler);
        reject(error);
      }
    };
    page.on("dialog", handler);
  });
}

async function cleanupTestData(page) {
  return page.evaluate(
    async ({ apiUrl, goalTitle, taskTitle }) => {
      const request = async (url, options = {}) => {
        const response = await fetch(url, options);
        if (!response.ok && response.status !== 404) {
          throw new Error(`${options.method ?? "GET"} ${url}: ${response.status}`);
        }
        return response.status === 204 ? null : response.json();
      };

      const [tasks, goals, plan, review] = await Promise.all([
        request(`${apiUrl}/tasks`),
        request(`${apiUrl}/goals`),
        request(`${apiUrl}/plans/today`),
        request(`${apiUrl}/reviews/weekly`),
      ]);
      if (
        review &&
        (review.snapshot?.completed_task_titles ?? []).includes(taskTitle)
      ) {
        await request(`${apiUrl}/reviews/weekly/${review.id}`, {
          method: "DELETE",
        });
      }
      if (
        plan &&
        plan.tasks.length > 0 &&
        plan.tasks.every((task) => task.title.startsWith("[验收]"))
      ) {
        await request(`${apiUrl}/plans/today`, { method: "DELETE" });
      }
      for (const task of tasks.filter((item) => item.title === taskTitle)) {
        await request(`${apiUrl}/tasks/${task.id}`, { method: "DELETE" });
      }
      for (const goal of goals.filter((item) => item.title === goalTitle)) {
        await request(`${apiUrl}/goals/${goal.id}`, { method: "DELETE" });
      }
      return { cleaned: true };
    },
    { apiUrl, goalTitle, taskTitle },
  );
}

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const goalScreenshot = path.join(
    projectRoot,
    "artifacts",
    "growth-goal-progress-verified.png",
  );
  const reviewScreenshot = path.join(
    projectRoot,
    "artifacts",
    "growth-weekly-review-verified.png",
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
      if (request.failure()?.errorText !== "net::ERR_ABORTED") {
        failedRequests.push(
          `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
        );
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 400) {
        badResponses.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto(`${baseUrl}/growth`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    await cleanupTestData(page);
    await page.reload({ waitUntil: "networkidle" });

    await page.getByRole("button", { name: "长期目标" }).click();
    await page.getByRole("button", { name: "+ 新建目标" }).click();
    await page.getByLabel("目标名称").fill(goalTitle);
    await page.locator(".growth-goal-form select").selectOption("technology");
    await page.getByRole("button", { name: "创建长期目标" }).click();

    let goalCard = page.locator(".growth-goal-card").filter({ hasText: goalTitle });
    await goalCard.waitFor({ state: "visible", timeout: 10_000 });
    await goalCard.getByRole("button", { name: "+ 添加里程碑" }).click();
    await goalCard.getByLabel("里程碑名称").fill("[验收] 完成数据层");
    await goalCard.getByRole("button", { name: "添加", exact: true }).click();
    await goalCard.getByText("[验收] 完成数据层", { exact: true }).waitFor();
    await goalCard.getByRole("button", { name: "+ 添加里程碑" }).click();
    await goalCard.getByLabel("里程碑名称").fill("[验收] 完成界面验收");
    await goalCard.getByRole("button", { name: "添加", exact: true }).click();
    await goalCard.getByText("[验收] 完成界面验收", { exact: true }).waitFor();

    await goalCard.getByRole("button", { name: "+ 添加关联任务" }).click();
    await page.getByLabel("任务名称").fill(taskTitle);
    await page.getByLabel("预计分钟").fill("45");
    await page.getByRole("button", { name: "创建任务" }).click();
    const taskCard = page.locator(".growth-task").filter({ hasText: taskTitle });
    await taskCard.first().waitFor({ state: "visible", timeout: 10_000 });

    await page.getByRole("button", { name: "生成 4 小时计划草稿" }).click();
    await page.getByText("等待你确认", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "确认今日计划" }).click();
    await page.getByText("今日计划已确认", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });

    await taskCard.first().getByRole("button", { name: "开始" }).click();
    await taskCard.first().getByText("进行中", { exact: true }).waitFor();
    const timeDialog = acceptDialogs(page, ["30"]);
    await taskCard.first().getByRole("button", { name: "记时" }).click();
    await timeDialog;
    await taskCard.first().getByText("已投入 30 分钟", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });

    const completionDialogs = acceptDialogs(page, [
      "45",
      "成长中心浏览器验收截图",
    ]);
    await taskCard
      .first()
      .getByRole("button", { name: `完成${taskTitle}` })
      .click();
    await completionDialogs;
    await taskCard.first().getByText("已完成", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });

    await page.getByRole("button", { name: "长期目标" }).click();
    goalCard = page.locator(".growth-goal-card").filter({ hasText: goalTitle });
    await goalCard
      .getByRole("button", { name: "[验收] 完成数据层标记完成" })
      .click();
    await goalCard.getByText("75%", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await page.screenshot({ path: goalScreenshot, fullPage: true });

    await page.getByRole("button", { name: "本周复盘" }).click();
    await page.getByRole("button", { name: "生成本周复盘" }).click();
    await page.getByText("100%", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await page
      .getByPlaceholder("本周做得好的地方、困难，以及下周需要调整的重点")
      .fill("验收确认：数字来自任务状态与 45 分钟真实计时。");
    await page.getByRole("button", { name: "确认本周复盘" }).click();
    await page.getByText("已确认", { exact: true }).waitFor({
      state: "visible",
      timeout: 10_000,
    });
    await page.screenshot({ path: reviewScreenshot, fullPage: true });

    await cleanupTestData(page);
    const cleanupState = await page.evaluate(async (apiUrl) => {
      const [overview, goals, tasks, plan, review] = await Promise.all([
        fetch(`${apiUrl}/growth/overview`).then((response) => response.json()),
        fetch(`${apiUrl}/goals`).then((response) => response.json()),
        fetch(`${apiUrl}/tasks`).then((response) => response.json()),
        fetch(`${apiUrl}/plans/today`).then((response) => response.json()),
        fetch(`${apiUrl}/reviews/weekly`).then((response) => response.json()),
      ]);
      return {
        overview,
        goalCount: goals.length,
        taskCount: tasks.length,
        hasPlan: plan !== null,
        hasReview: review !== null,
      };
    }, apiUrl);

    console.log(
      JSON.stringify(
        {
          goalCreated: true,
          milestonesCreated: 2,
          traceableProgress: "75%",
          dailyPlanDraftConfirmed: true,
          taskLifecycleVerified: true,
          realMinutesInReview: 45,
          weeklyReviewConfirmed: true,
          cleanupState,
          consoleMessages,
          pageErrors,
          failedRequests,
          badResponses,
          goalScreenshot,
          reviewScreenshot,
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
