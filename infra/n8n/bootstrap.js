"use strict";

const fs = require("node:fs");
const path = require("node:path");

const baseUrl = "http://127.0.0.1:5678";
const email = "jarvis-automation@local.invalid";
const password = fs
  .readFileSync("/run/secrets/n8n_owner_password")
  .toString("utf8")
  .trim();
const workflowDirectory = "/opt/jarvis/workflows";
let cookie = "";

function unwrap(value) {
  return value && typeof value === "object" && "data" in value
    ? value.data
    : value;
}

async function waitForN8n() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const readiness = await fetch(`${baseUrl}/healthz/readiness`);
      const rest = await fetch(`${baseUrl}/rest/login`);
      const contentType = rest.headers.get("content-type") || "";
      if (readiness.ok && rest.status !== 404 && contentType.includes("json")) {
        return;
      }
    } catch {
      // n8n is still applying its private SQLite migrations.
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error("n8n did not become ready for local bootstrap");
}

function captureCookie(response) {
  const setCookie = response.headers.get("set-cookie") || "";
  cookie = setCookie.split(";")[0];
  if (!cookie.includes("=")) {
    throw new Error(
      `n8n did not issue an owner cookie (HTTP ${response.status}, ${response.headers.get("content-type") || "unknown content"})`,
    );
  }
}

async function jsonRequest(route, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-N8N-BROWSER-ID": "jarvis-local-bootstrap",
    ...(options.headers || {}),
  };
  if (cookie) headers.Cookie = cookie;
  const response = await fetch(`${baseUrl}${route}`, { ...options, headers });
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new Error(`n8n returned non-JSON bootstrap response: HTTP ${response.status}`);
    }
  }
  if (!response.ok) {
    const message = JSON.stringify(payload).slice(0, 500);
    throw new Error(`n8n bootstrap request failed: HTTP ${response.status} ${message}`);
  }
  return { payload: unwrap(payload), response };
}

async function authenticateOwner() {
  const setupResponse = await fetch(`${baseUrl}/rest/owner/setup`, {
    body: JSON.stringify({
      email,
      firstName: "Jarvis",
      lastName: "Automation",
      password,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-N8N-BROWSER-ID": "jarvis-local-bootstrap",
    },
    method: "POST",
  });
  if (setupResponse.ok) {
    captureCookie(setupResponse);
    return;
  }
  if (setupResponse.status !== 400) {
    const detail = (await setupResponse.text()).slice(0, 300);
    throw new Error(
      `n8n owner setup failed: HTTP ${setupResponse.status} ${detail}`,
    );
  }
  const login = await jsonRequest("/rest/login", {
    body: JSON.stringify({ emailOrLdapLoginId: email, password }),
    method: "POST",
  });
  captureCookie(login.response);
}

async function publishWorkflows() {
  const files = fs
    .readdirSync(workflowDirectory)
    .filter((file) => file.endsWith(".json"))
    .sort();
  const published = [];
  for (const file of files) {
    const source = JSON.parse(
      fs.readFileSync(path.join(workflowDirectory, file), "utf8"),
    );
    const body = {
      active: false,
      connections: source.connections,
      name: source.name,
      nodes: source.nodes,
      pinData: {},
      settings: source.settings,
      tags: [],
    };
    const created = await jsonRequest("/rest/workflows", {
      body: JSON.stringify(body),
      method: "POST",
    });
    const workflow = created.payload;
    if (!workflow?.id || !workflow?.versionId) {
      throw new Error(`n8n did not return an ID and version for ${file}`);
    }
    await jsonRequest(`/rest/workflows/${workflow.id}/activate`, {
      body: JSON.stringify({
        description: "Jarvis Sprint 30 isolated sandbox workflow",
        name: source.name,
        versionId: workflow.versionId,
      }),
      method: "POST",
    });
    published.push({ file, id: workflow.id, versionId: workflow.versionId });
  }
  fs.writeFileSync(
    "/home/node/.n8n/jarvis-published-workflows.json",
    JSON.stringify(published, null, 2),
  );
}

async function main() {
  if (password.length < 32) throw new Error("n8n owner password is missing or too short");
  await waitForN8n();
  await authenticateOwner();
  await publishWorkflows();
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
