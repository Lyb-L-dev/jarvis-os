"use client";

import { useCallback, useEffect, useState } from "react";

import {
  BackupListResponse,
  createSystemBackup,
  downloadUserDataExport,
  listSystemBackups,
  verifySystemBackup,
} from "@/lib/api";
import { formatDateTimeMedium } from "@/lib/utils";

function formatDate(value?: string | null) {
  return formatDateTimeMedium(value, "尚未验证");
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DataProtection() {
  const [data, setData] = useState<BackupListResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await listSystemBackups(signal);
      setData(result);
      setError(null);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "无法读取备份状态。");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  async function createBackup() {
    setBusy("create");
    setNotice(null);
    setError(null);
    try {
      await createSystemBackup();
      await load();
      setNotice("本地数据库备份已创建，并通过文件完整性校验。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建备份失败。");
    } finally {
      setBusy(null);
    }
  }

  async function verifyBackup(backupId: string) {
    setBusy(backupId);
    setNotice(null);
    setError(null);
    try {
      await verifySystemBackup(backupId);
      await load();
      setNotice("已在临时数据库中完成恢复验证，当前数据没有被修改。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "恢复验证失败。");
    } finally {
      setBusy(null);
    }
  }

  async function exportData() {
    setBusy("export");
    setNotice(null);
    setError(null);
    try {
      await downloadUserDataExport();
      setNotice("个人数据已导出为本地 JSON 文件，文件中不包含 API Key。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "导出个人数据失败。");
    } finally {
      setBusy(null);
    }
  }

  if (!data && !error) {
    return <div className="backup-loading">正在检查数据保护状态…</div>;
  }

  const latest = data?.status.latest_backup;

  return (
    <div className="backup-center">
      <div className="backup-summary-grid">
        <article>
          <span>自动备份</span>
          <strong>{data?.status.enabled ? "已启用" : "已停用"}</strong>
          <small>Jarvis 运行时每小时检查，约每天生成一次</small>
        </article>
        <article>
          <span>最近备份</span>
          <strong>{latest ? formatDate(latest.created_at) : "尚无备份"}</strong>
          <small>最多保留 {data?.status.retention_count ?? 30} 份</small>
        </article>
        <article>
          <span>恢复验证</span>
          <strong>
            {latest?.restore_verified_at ? "已通过" : "等待首次验证"}
          </strong>
          <small>
            {latest?.restore_verified_at
              ? formatDate(latest.restore_verified_at)
              : "验证不会覆盖当前数据库"}
          </small>
        </article>
      </div>

      <div className="backup-location">
        <div>
          <span>本地保存位置</span>
          <code>{data?.status.backup_directory ?? "backups"}</code>
        </div>
        <div className="backup-actions">
          <button
            disabled={busy !== null}
            onClick={() => void exportData()}
            type="button"
          >
            {busy === "export" ? "导出中…" : "导出个人数据"}
          </button>
          <button
            className="primary-action"
            disabled={busy !== null || !data?.status.enabled}
            onClick={() => void createBackup()}
            type="button"
          >
            {busy === "create" ? "备份中…" : "立即备份"}
          </button>
        </div>
      </div>

      {notice ? <div className="backup-notice success">{notice}</div> : null}
      {error ? <div className="backup-notice error">{error}</div> : null}
      {data?.status.worker_error ? (
        <div className="backup-notice warning">
          自动备份最近一次异常：{data.status.worker_error}
        </div>
      ) : null}

      <div className="backup-list">
        <div className="backup-list-heading">
          <div>
            <span className="eyebrow">RECOVERY POINTS</span>
            <h4>本地恢复点</h4>
          </div>
          <span>{data?.status.backup_count ?? 0} 份</span>
        </div>

        {data?.backups.length ? (
          data.backups.slice(0, 8).map((backup) => (
            <article className="backup-row" key={backup.id}>
              <div className="backup-row-main">
                <strong>{formatDate(backup.created_at)}</strong>
                <span>
                  {formatSize(backup.size_bytes)} · 数据结构{" "}
                  {backup.alembic_version ?? "未知"}
                </span>
                <code>{backup.sha256.slice(0, 16)}…</code>
              </div>
              <div className="backup-row-state">
                <span
                  className={
                    backup.restore_verified_at
                      ? "backup-verified"
                      : "backup-unverified"
                  }
                >
                  {backup.restore_verified_at
                    ? `恢复验证通过 · ${backup.verified_table_count ?? "?"} 张表`
                    : "仅完成完整性校验"}
                </span>
                <button
                  disabled={busy !== null}
                  onClick={() => void verifyBackup(backup.id)}
                  type="button"
                >
                  {busy === backup.id ? "验证中…" : "验证可恢复"}
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className="backup-empty">
            还没有本地恢复点。点击“立即备份”创建第一份。
          </div>
        )}
      </div>

      <p className="backup-boundary">
        为避免误操作，网页不提供“覆盖恢复”按钮。真正恢复时必须先停止
        Jarvis、验证备份，并输入完整确认文字；恢复前还会自动保留当前数据库。
        同一块硬盘损坏时本地备份也会丢失，后续可以再配置移动硬盘副本。
      </p>
    </div>
  );
}
