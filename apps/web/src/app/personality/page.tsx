import { PersonalityLayer } from "@/components/personality-layer";

export default function PersonalityPage() {
  return (
    <main className="dashboard personality-page">
      <header className="topbar personality-topbar">
        <div>
          <div className="eyebrow">IDENTITY PLANE · SPRINT 35</div>
          <h1>
            Personality <span>Layer</span>
          </h1>
          <p className="page-description">
            Jarvis 有稳定的人格：称呼、语气和表达习惯在中文与英文中保持一致。
            人格只影响表达，绝不覆盖事实、安全规则和你的最新要求。
          </p>
        </div>
        <div className="observatory-live-badge">
          <i /> CONSISTENT IDENTITY
        </div>
      </header>
      <PersonalityLayer />
    </main>
  );
}
