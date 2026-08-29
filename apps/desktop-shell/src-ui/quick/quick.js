const { invoke } = window.__TAURI__.core;
const runtime = window.__JARVIS_RUNTIME__;
const apiBase = runtime?.apiBaseUrl;
const sessionHeaders = runtime?.sessionToken
  ? { "X-Jarvis-Desktop-Session": runtime.sessionToken }
  : {};

const form = document.querySelector("#quick-form");
const input = document.querySelector("#quick-input");
const sendButton = document.querySelector("#send-button");
const hideButton = document.querySelector("#hide-button");
const answerPanel = document.querySelector("#answer-panel");
const answerText = document.querySelector("#answer-text");
const answerState = document.querySelector("#answer-state");
const continueButton = document.querySelector("#continue-button");
const feedback = document.querySelector("#feedback");
const fileInput = document.querySelector("#file-input");
const filePreview = document.querySelector("#file-preview");
const fileName = document.querySelector("#file-name");
const fileMeta = document.querySelector("#file-meta");
const fileCancel = document.querySelector("#file-cancel");
const fileConfirm = document.querySelector("#file-confirm");
const voiceButton = document.querySelector("#voice-button");
const voiceLabel = document.querySelector("#voice-label");

const SESSION_TTL_MS = 30 * 60 * 1000;
const MAX_FILE_BYTES = 2 * 1024 * 1024;
const RECORDING_TIMEOUT_MS = 60 * 1000;
let conversationId = null;
let lastInteractionAt = 0;
let currentRequest = null;
let currentRequestId = null;
let pendingFile = null;
let forceLocalMode = false;
let recorder = null;
let audioChunks = [];
let voiceAvailable = false;
let recordingTimer = null;
let voiceHeld = false;

function recordReliability(kind, outcome, durationMs = null) {
  void invoke("desktop_record_reliability_event", {
    input: { kind, outcome, durationMs, stage: null },
  }).catch(() => {});
}

function clearRecordingTimer() {
  if (recordingTimer) clearTimeout(recordingTimer);
  recordingTimer = null;
}

function abortRecording(message) {
  const activeRecorder = recorder;
  voiceHeld = false;
  clearRecordingTimer();
  recorder = null;
  audioChunks = [];
  if (activeRecorder) {
    activeRecorder.onstop = null;
    if (activeRecorder.state === "recording") activeRecorder.stop();
    activeRecorder.stream.getTracks().forEach((track) => track.stop());
  }
  voiceButton.classList.remove("is-listening");
  voiceButton.setAttribute("aria-pressed", "false");
  voiceLabel.textContent = "按住说话";
  if (message) showFeedback(message, true);
  if (activeRecorder) recordReliability("voice_transcription", "cancelled");
}

function showFeedback(message, isError = false) {
  feedback.textContent = message;
  feedback.style.color = isError ? "#e5a1a1" : "";
}

function requestHeaders(json = false) {
  return json
    ? { ...sessionHeaders, "Content-Type": "application/json" }
    : { ...sessionHeaders };
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      ...requestHeaders(Boolean(options.body)),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

async function ensureConversation(mode) {
  const expired = Date.now() - lastInteractionAt >= SESSION_TTL_MS;
  if (conversationId && !expired) return conversationId;
  const created = await apiRequest("/chat/conversations", {
    method: "POST",
    body: JSON.stringify({ title: "快速对话", model_mode: mode }),
  });
  conversationId = created.id;
  lastInteractionAt = Date.now();
  return conversationId;
}

function showAnswer(state, text = "") {
  answerPanel.hidden = false;
  answerState.textContent = state;
  answerText.textContent = text;
  continueButton.hidden = !conversationId;
}

async function routingPreview(content, mode) {
  return apiRequest("/chat/routing/preview", {
    method: "POST",
    body: JSON.stringify({
      content,
      mode,
      sensitive: forceLocalMode,
      paid_call_confirmed: false,
    }),
  });
}

function parseEventBlock(rawBlock, handlers) {
  const block = rawBlock.replaceAll("\r\n", "\n").trim();
  if (!block) return;
  let eventName = "message";
  const dataLines = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return;
  handlers(eventName, JSON.parse(dataLines.join("\n")));
}

async function streamMessage(targetConversation, content, mode, requestId, signal) {
  const response = await fetch(`${apiBase}/chat/conversations/${targetConversation}/stream`, {
    method: "POST",
    headers: requestHeaders(true),
    body: JSON.stringify({
      content,
      mode,
      sensitive: forceLocalMode,
      request_id: requestId,
      paid_call_confirmed: false,
      use_knowledge: !forceLocalMode,
    }),
    signal,
  });
  if (!response.ok) {
    let detail = `发送失败（${response.status}）`;
    try { detail = (await response.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  if (!response.body) throw new Error("无法建立流式连接。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let completed = false;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      parseEventBlock(buffer.slice(0, boundary), (eventName, payload) => {
        if (eventName === "delta" && payload.content) {
          answer += payload.content;
          showAnswer("正在回答", answer);
        } else if (eventName === "error") {
          throw new Error(payload.message || "生成回复时发生错误。");
        } else if (eventName === "done") {
          completed = true;
          answer = payload.assistant_message?.content || answer;
          showAnswer("回答完成", answer);
        }
      });
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  if (!completed && !signal.aborted) throw new Error("流式连接提前结束，请重试。");
  return answer;
}

async function submitDraft() {
  const content = input.value.trim();
  if (!content || currentRequest) return;
  const mode = forceLocalMode ? "local" : "standard";
  const startedAt = performance.now();
  const fileAnalysis = forceLocalMode;
  recordReliability("quick_send", "attempted");
  showFeedback("正在检查是否需要主窗口确认…");
  const route = await routingPreview(content, mode);
  if (route && route.disposition !== "allow_automatically") {
    showAnswer("需要确认", "这个请求涉及审批、工具或外部影响，请在主窗口中确认后继续。快速窗口不会提供批准按钮。 ");
    continueButton.hidden = false;
    showFeedback("草稿已保留，尚未发送。", false);
    recordReliability("quick_send", "cancelled", Math.round(performance.now() - startedAt));
    return;
  }

  const targetConversation = await ensureConversation(mode);
  const requestId = crypto.randomUUID();
  const controller = new AbortController();
  currentRequest = controller;
  currentRequestId = requestId;
  sendButton.disabled = true;
  showAnswer("正在思考", "");
  showFeedback(forceLocalMode ? "文件正文只发送到本地模型。" : "已进入标准对话事实源。");
  try {
    await streamMessage(targetConversation, content, mode, requestId, controller.signal);
    lastInteractionAt = Date.now();
    input.value = "";
    forceLocalMode = false;
    showFeedback("已同步到主工作台。30 分钟内继续此快速对话。");
    recordReliability("quick_send", "succeeded", Math.round(performance.now() - startedAt));
    if (fileAnalysis) recordReliability("file_analyze", "succeeded", Math.round(performance.now() - startedAt));
  } catch (error) {
    if (!controller.signal.aborted) {
      showFeedback(error instanceof Error ? error.message : "发送失败，草稿已保留。", true);
      answerState.textContent = "发送失败";
    }
    recordReliability(
      "quick_send",
      controller.signal.aborted ? "cancelled" : "failed",
      Math.round(performance.now() - startedAt),
    );
    if (fileAnalysis) recordReliability("file_analyze", controller.signal.aborted ? "cancelled" : "failed", Math.round(performance.now() - startedAt));
  } finally {
    currentRequest = null;
    currentRequestId = null;
    sendButton.disabled = false;
  }
}

async function cancelAndHide() {
  abortRecording();
  if (currentRequest) {
    const requestId = currentRequestId;
    currentRequest.abort();
    if (requestId) {
      void apiRequest(`/chat/streams/${requestId}/cancel`, { method: "POST" }).catch(() => {});
    }
    showFeedback("已停止等待；服务端结果以主工作台记录为准。草稿仍保留。");
  }
  await invoke("quick_hide");
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void submitDraft().catch((error) => showFeedback(String(error), true));
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") void cancelAndHide();
});

hideButton.addEventListener("click", () => void cancelAndHide());

continueButton.addEventListener("click", async () => {
  try {
    await invoke("quick_continue_in_main", {
      conversationId,
      draft: input.value,
    });
  } catch (error) {
    showFeedback(String(error), true);
  }
});

fileInput.addEventListener("change", () => {
  const [file] = fileInput.files || [];
  if (!file) return;
  pendingFile = file;
  const extension = file.name.toLowerCase().split(".").pop();
  const supported = ["md", "txt"].includes(extension || "") && file.size <= MAX_FILE_BYTES;
  fileName.textContent = file.name;
  fileMeta.textContent = `${(file.size / 1024).toFixed(1)} KiB · ${extension?.toUpperCase() || "未知类型"}`;
  fileConfirm.disabled = !supported;
  fileConfirm.textContent = supported ? "读取到草稿" : "不支持此文件";
  filePreview.hidden = false;
  showFeedback(
    supported ? "尚未读取文件正文。" : "仅支持单个 UTF-8 .md/.txt 文件，且不超过 2 MiB。",
    !supported,
  );
  recordReliability("file_preview", supported ? "succeeded" : "failed");
});

fileCancel.addEventListener("click", () => {
  pendingFile = null;
  fileInput.value = "";
  filePreview.hidden = true;
  showFeedback("已取消，未读取文件正文。");
  recordReliability("file_reject", "succeeded");
});

fileConfirm.addEventListener("click", async () => {
  if (!pendingFile) return;
  fileConfirm.disabled = true;
  try {
    const bytes = await pendingFile.arrayBuffer();
    const content = new TextDecoder("utf-8", { fatal: true }).decode(bytes).replace(/^\uFEFF/, "");
    input.value = `请仅使用本地模型分析以下文件，不要自动加入知识库。\n\n文件名：${pendingFile.name}\n\n${content}`;
    forceLocalMode = true;
    filePreview.hidden = true;
    showFeedback("文件已读入可编辑草稿；确认内容后再发送，本次强制使用本地模型。");
    recordReliability("file_confirm", "succeeded");
    input.focus();
  } catch {
    showFeedback("文件不是有效的 UTF-8/UTF-8 BOM 文本，已拒绝读取。", true);
    recordReliability("file_confirm", "failed");
  } finally {
    pendingFile = null;
    fileInput.value = "";
    fileConfirm.disabled = false;
  }
});

async function recordingToPcmWave(recording) {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await recording.arrayBuffer());
    const mono = new Float32Array(decoded.length);
    for (let channel = 0; channel < decoded.numberOfChannels; channel += 1) {
      const data = decoded.getChannelData(channel);
      for (let index = 0; index < data.length; index += 1) mono[index] += data[index] / decoded.numberOfChannels;
    }
    const targetLength = Math.max(1, Math.round(mono.length * 16000 / decoded.sampleRate));
    const samples = new Float32Array(targetLength);
    const scale = (mono.length - 1) / Math.max(1, targetLength - 1);
    for (let index = 0; index < targetLength; index += 1) {
      const position = index * scale;
      const left = Math.floor(position);
      const right = Math.min(left + 1, mono.length - 1);
      samples[index] = mono[left] + (mono[right] - mono[left]) * (position - left);
    }
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const write = (offset, text) => [...text].forEach((character, index) => view.setUint8(offset + index, character.charCodeAt(0)));
    write(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); write(8, "WAVEfmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    write(36, "data"); view.setUint32(40, samples.length * 2, true);
    samples.forEach((sample, index) => {
      const value = Math.max(-1, Math.min(1, sample));
      view.setInt16(44 + index * 2, value < 0 ? value * 32768 : value * 32767, true);
    });
    return new Blob([buffer], { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

async function startRecording() {
  if (!voiceAvailable || recorder) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    if (!voiceHeld) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    const activeRecorder = new MediaRecorder(stream);
    recorder = activeRecorder;
    audioChunks = [];
    activeRecorder.ondataavailable = (event) => { if (event.data.size) audioChunks.push(event.data); };
    activeRecorder.onstop = async () => {
      clearRecordingTimer();
      if (recorder !== activeRecorder) return;
      recorder = null;
      stream.getTracks().forEach((track) => track.stop());
      const recording = new Blob(audioChunks, { type: activeRecorder.mimeType });
      audioChunks = [];
      voiceButton.classList.remove("is-listening");
      voiceButton.setAttribute("aria-pressed", "false");
      voiceLabel.textContent = "按住说话";
      if (!recording.size) return;
      showFeedback("正在本地转写；不会自动发送。", false);
      const transcriptionStartedAt = performance.now();
      try {
        const wav = await recordingToPcmWave(recording);
        const response = await fetch(`${apiBase}/voice/transcriptions`, { method: "POST", headers: { ...sessionHeaders, "Content-Type": "audio/wav" }, body: wav });
        if (!response.ok) throw new Error((await response.json()).detail || "本地转写失败。");
        const result = await response.json();
        input.value = result.text;
        input.focus();
        showFeedback("转写已放入草稿，请编辑确认后发送。", false);
        recordReliability("voice_transcription", "succeeded", Math.round(performance.now() - transcriptionStartedAt));
      } catch (error) {
        showFeedback(String(error), true);
        recordReliability("voice_transcription", "failed", Math.round(performance.now() - transcriptionStartedAt));
      }
    };
    activeRecorder.onerror = () => abortRecording("麦克风录音中断，录音已取消，草稿不会自动发送。");
    stream.getTracks().forEach((track) => {
      track.onended = () => {
        if (recorder === activeRecorder) {
          abortRecording("麦克风连接已断开，录音已取消，草稿不会自动发送。");
        }
      };
    });
    activeRecorder.start();
    recordingTimer = setTimeout(() => {
      if (recorder === activeRecorder) {
        abortRecording("录音已达到 60 秒上限并安全取消，草稿不会自动发送。");
      }
    }, RECORDING_TIMEOUT_MS);
    voiceButton.classList.add("is-listening");
    voiceButton.setAttribute("aria-pressed", "true");
    voiceLabel.textContent = "松开转写";
    showFeedback("正在本地录音，松开后转写。", false);
  } catch (error) {
    showFeedback(error?.name === "NotAllowedError" ? "麦克风权限被拒绝，请在 Windows 隐私设置中允许后重试。" : "麦克风不可用，请检查设备。", true);
    recordReliability("voice_permission", "failed");
  }
}

function stopRecording() {
  voiceHeld = false;
  if (recorder?.state === "recording") recorder.stop();
}

voiceButton.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  voiceButton.setPointerCapture(event.pointerId);
  voiceHeld = true;
  void startRecording();
});
voiceButton.addEventListener("pointerup", stopRecording);
voiceButton.addEventListener("pointercancel", () => abortRecording("录音已取消，草稿不会自动发送。"));
voiceButton.addEventListener("keydown", (event) => {
  if ((event.key === " " || event.key === "Enter") && !event.repeat) { event.preventDefault(); voiceHeld = true; void startRecording(); }
});
voiceButton.addEventListener("keyup", (event) => {
  if (event.key === " " || event.key === "Enter") { event.preventDefault(); stopRecording(); }
});

window.addEventListener("jarvis:quick-voice-start", () => {
  if (!voiceButton.disabled) { voiceHeld = true; void startRecording(); }
});
window.addEventListener("jarvis:quick-voice-stop", stopRecording);

async function initialize() {
  if (!apiBase) {
    sendButton.disabled = true;
    showFeedback("Jarvis Core 尚未就绪。", true);
    return;
  }
  try {
    const status = await apiRequest("/voice/status");
    voiceAvailable = Boolean(status.enabled && status.stt_ready);
    voiceButton.disabled = !voiceAvailable;
    if (!voiceAvailable) voiceButton.title = "本地语音未启用或 STT 模型未就绪";
    recordReliability("voice_model", voiceAvailable ? "succeeded" : "not_configured");
  } catch {
    voiceButton.disabled = true;
    recordReliability("voice_model", "failed");
  }
  input.focus();
}

initialize();
