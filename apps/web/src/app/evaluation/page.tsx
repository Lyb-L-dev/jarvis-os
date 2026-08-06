import { EvaluationCenter } from "@/components/evaluation-center";

export default function EvaluationPage() {
  return (
    <main className="dashboard evaluation-page">
      <header className="topbar">
        <div>
          <div className="eyebrow">PERSONAL MODEL LAB</div>
          <h1>
            模型 <span>评测</span>
          </h1>
          <p className="page-description">
            用你的真实使用场景比较 MiMo、本地 Qwen 和 DeepSeek，
            路由规则与付费确认不会被自动改变。
          </p>
        </div>
      </header>
      <EvaluationCenter />
    </main>
  );
}
