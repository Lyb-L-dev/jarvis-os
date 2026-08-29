"use client";

import { useEffect, useState } from "react";
import { FileText, ShieldCheck, X } from "lucide-react";

type FilePreview = {
  token: string;
  name: string;
  extension: string;
  sizeBytes: number;
  source: string;
  localOnly: boolean;
  knowledgeWrite: boolean;
  expiresInSeconds: number;
};

type DesktopActivation = {
  kind?: string;
  preview?: FilePreview;
  message?: string;
};

type FileContent = {
  name: string;
  content: string;
  localOnly: boolean;
  knowledgeWrite: boolean;
};

type TauriCore = {
  invoke: <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
};

function tauriCore(): TauriCore | null {
  return (window as typeof window & { __TAURI__?: { core?: TauriCore } }).__TAURI__?.core ?? null;
}

function formatBytes(value: number) {
  return value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KiB`;
}

export function DesktopFileHandoff() {
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const consume = (detail?: DesktopActivation | null) => {
      if (detail?.kind === "file" && detail.preview) {
        setPreview(detail.preview);
        setError(null);
      } else if (detail?.kind === "file-error") {
        setPreview(null);
        setError(detail.message ?? "这个文件无法交给 Jarvis。 ");
      } else {
        return;
      }
      delete (window as typeof window & { __JARVIS_DESKTOP_ACTIVATION__?: DesktopActivation }).__JARVIS_DESKTOP_ACTIVATION__;
    };
    const target = window as typeof window & { __JARVIS_DESKTOP_ACTIVATION__?: DesktopActivation };
    consume(target.__JARVIS_DESKTOP_ACTIVATION__);
    const listener = (event: Event) => consume((event as CustomEvent<DesktopActivation>).detail);
    window.addEventListener("jarvis:desktop-activation", listener);
    return () => window.removeEventListener("jarvis:desktop-activation", listener);
  }, []);

  async function close() {
    if (preview) {
      await tauriCore()?.invoke("desktop_file_cancel", { token: preview.token }).catch(() => undefined);
    }
    setPreview(null);
    setError(null);
  }

  async function confirm() {
    if (!preview) return;
    const core = tauriCore();
    if (!core) {
      setError("受控文件读取仅在 Jarvis Windows App 中可用。");
      return;
    }
    setBusy(true);
    try {
      const file = await core.invoke<FileContent>("desktop_file_read", { token: preview.token });
      const draft = [
        "请仅使用本地模型分析以下文件，不要自动加入知识库，也不要修改源文件。",
        "",
        `文件名：${file.name}`,
        "",
        file.content,
      ].join("\n");
      window.dispatchEvent(new CustomEvent("jarvis:open-conversation", {
        detail: { draft, localOnly: true, fileAnalysis: true },
      }));
      setPreview(null);
      setError(null);
    } catch (readError) {
      setPreview(null);
      setError(String(readError));
    } finally {
      setBusy(false);
    }
  }

  if (!preview && !error) return null;

  return (
    <div className="desktop-file-scrim" role="presentation">
      <section
        aria-labelledby="desktop-file-title"
        aria-modal="true"
        className="desktop-file-dialog"
        role="dialog"
      >
        <button aria-label="关闭文件预览" className="desktop-file-close" onClick={() => void close()} type="button">
          <X aria-hidden="true" />
        </button>
        <div className="desktop-file-icon" aria-hidden="true">
          <FileText />
        </div>
        <p className="eyebrow">CONTROLLED FILE HANDOFF</p>
        <h2 id="desktop-file-title">{error ? "无法接入这个文件" : "交给 Jarvis 前请确认"}</h2>
        {preview ? (
          <>
            <dl className="desktop-file-facts">
              <div><dt>文件</dt><dd>{preview.name}</dd></div>
              <div><dt>类型与大小</dt><dd>.{preview.extension} · {formatBytes(preview.sizeBytes)}</dd></div>
              <div><dt>来源</dt><dd>{preview.source}</dd></div>
            </dl>
            <div className="desktop-file-safety">
              <ShieldCheck aria-hidden="true" />
              <p>
                <strong>确认后才读取正文</strong>
                <span>本次强制本地分析，不上传、不修改源文件、不写入知识库。授权会在 10 分钟后失效。</span>
              </p>
            </div>
            <div className="desktop-file-actions">
              <button disabled={busy} onClick={() => void close()} type="button">取消</button>
              <button className="desktop-file-primary" disabled={busy} onClick={() => void confirm()} type="button">
                {busy ? "正在安全读取…" : "读取到可编辑草稿"}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="desktop-file-error">{error}</p>
            <p className="desktop-file-hint">V4 仅支持本机单个 UTF-8 / UTF-8 BOM 的 .md 或 .txt 文件，且不超过 2 MiB。</p>
            <div className="desktop-file-actions">
              <button className="desktop-file-primary" onClick={() => void close()} type="button">我知道了</button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
