"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");

const port = Number(process.env.INGRESS_PORT || 5680);
const targetBase = process.env.N8N_INTERNAL_URL || "http://jarvis-n8n:5678";
const secret = fs
  .readFileSync("/run/secrets/jarvis_webhook_secret")
  .toString("utf8")
  .trim();
const maxBodyBytes = 65_536;
const maxSkewSeconds = 60;
const allowedPaths = new Map([
  ["/v1/status", "/webhook/jarvis-provider-status"],
  ["/v1/calendar/read", "/webhook/jarvis-calendar-read"],
  ["/v1/email/draft", "/webhook/jarvis-email-draft"],
]);
const usedNonces = new Map();

if (secret.length < 32) {
  throw new Error("Jarvis webhook secret is missing or too short");
}

function sendJson(response, status, body) {
  const encoded = Buffer.from(JSON.stringify(body));
  response.writeHead(status, {
    "Content-Length": encoded.length,
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(encoded);
}

function safeEqualHex(actual, expected) {
  if (!/^[a-f0-9]{64}$/i.test(actual || "")) return false;
  const actualBytes = Buffer.from(actual, "hex");
  const expectedBytes = Buffer.from(expected, "hex");
  return (
    actualBytes.length === expectedBytes.length &&
    crypto.timingSafeEqual(actualBytes, expectedBytes)
  );
}

function pruneNonces(nowSeconds) {
  for (const [nonce, seenAt] of usedNonces.entries()) {
    if (nowSeconds - seenAt > maxSkewSeconds) usedNonces.delete(nonce);
  }
}

async function forward(response, targetPath, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const upstream = await fetch(`${targetBase}${targetPath}`, {
      body,
      headers: {
        "Content-Type": "application/json",
        "X-Jarvis-Verified": "hmac-sha256",
      },
      method: "POST",
      redirect: "manual",
      signal: controller.signal,
    });
    const result = Buffer.from(await upstream.arrayBuffer());
    if (result.length > 131_072) {
      sendJson(response, 502, { error: "upstream_response_too_large" });
      return;
    }
    response.writeHead(upstream.status, {
      "Content-Length": result.length,
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    });
    response.end(result);
  } catch {
    sendJson(response, 503, { error: "n8n_unavailable" });
  } finally {
    clearTimeout(timeout);
  }
}

const server = http.createServer((request, response) => {
  if (request.method === "GET" && request.url === "/healthz") {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2_000);
    fetch(`${targetBase}/healthz/readiness`, { signal: controller.signal })
      .then((upstream) =>
        sendJson(response, upstream.ok ? 200 : 503, {
          ingress: "ready",
          n8n: upstream.ok ? "ready" : "unavailable",
        }),
      )
      .catch(() =>
        sendJson(response, 503, { ingress: "ready", n8n: "unavailable" }),
      )
      .finally(() => clearTimeout(timeout));
    return;
  }

  const targetPath = allowedPaths.get(request.url || "");
  if (request.method !== "POST" || !targetPath) {
    sendJson(response, 404, { error: "route_not_allowed" });
    return;
  }

  const chunks = [];
  let size = 0;
  request.on("data", (chunk) => {
    size += chunk.length;
    if (size > maxBodyBytes) {
      request.destroy();
      return;
    }
    chunks.push(chunk);
  });
  request.on("end", () => {
    if (size > maxBodyBytes) {
      sendJson(response, 413, { error: "payload_too_large" });
      return;
    }
    const body = Buffer.concat(chunks);
    const timestamp = request.headers["x-jarvis-timestamp"];
    const nonce = request.headers["x-jarvis-nonce"];
    const signature = request.headers["x-jarvis-signature"];
    const keyId = request.headers["x-jarvis-key-id"];
    const signedAt = Number(timestamp);
    const now = Math.floor(Date.now() / 1000);
    pruneNonces(now);
    if (
      keyId !== "jarvis-core-v1" ||
      !Number.isInteger(signedAt) ||
      Math.abs(now - signedAt) > maxSkewSeconds ||
      typeof nonce !== "string" ||
      !/^[a-f0-9]{32}$/i.test(nonce) ||
      usedNonces.has(nonce)
    ) {
      sendJson(response, 401, { error: "invalid_or_replayed_signature" });
      return;
    }
    const bodyHash = crypto.createHash("sha256").update(body).digest("hex");
    const canonical = [timestamp, nonce, "POST", request.url, bodyHash].join("\n");
    const expected = crypto
      .createHmac("sha256", secret)
      .update(canonical)
      .digest("hex");
    if (!safeEqualHex(signature, expected)) {
      sendJson(response, 401, { error: "invalid_or_replayed_signature" });
      return;
    }
    try {
      JSON.parse(body.toString("utf8"));
    } catch {
      sendJson(response, 400, { error: "invalid_json" });
      return;
    }
    usedNonces.set(nonce, now);
    void forward(response, targetPath, body);
  });
});

server.requestTimeout = 15_000;
server.headersTimeout = 5_000;
server.listen(port, "0.0.0.0");
