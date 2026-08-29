import Link from "next/link";

import { DataProtection } from "@/components/data-protection";
import { DesktopSettings } from "@/components/desktop-settings";
import { ModelCallHistory } from "@/components/model-call-history";
import { SystemStatus } from "@/components/system-status";

export default function SettingsPage() {
  return (
    <main className="dashboard settings-page">
      <header className="topbar">
        <div>
          <div className="eyebrow">SYSTEM CONFIGURATION</div>
          <h1>
            Jarvis <span>设置</span>
          </h1>
        </div>
      </header>

      <section className="panel settings-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">CORE STATUS</div>
            <h3>系统连接</h3>
          </div>
        </div>
        <SystemStatus />
        <p className="settings-note">
          API Key 只从本机 .env 读取，页面不会显示密钥内容。
        </p>
      </section>

      <DesktopSettings />

      <section className="panel settings-panel data-protection-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">DATA PROTECTION</div>
            <h3>自动备份与恢复验证</h3>
          </div>
          <span className="settings-safe-label">仅保存在本机</span>
        </div>
        <DataProtection />
      </section>

      <section className="panel settings-panel knowledge-settings-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">LOCAL KNOWLEDGE</div>
            <h3>Obsidian 知识库</h3>
          </div>
          <span className="settings-safe-label">仅访问 Vault/Jarvis</span>
        </div>
        <p className="settings-note">
          连接、扫描和搜索均在本机完成，不依赖社区插件、MCP 或云端同步。
        </p>
        <Link className="primary-button knowledge-settings-link" href="/knowledge">
          打开知识库设置
        </Link>
      </section>

      <section className="panel settings-panel call-history-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">MODEL AUDIT</div>
            <h3>最近模型调用</h3>
          </div>
          <span className="settings-safe-label">不记录密钥</span>
        </div>
        <ModelCallHistory />
      </section>
    </main>
  );
}
