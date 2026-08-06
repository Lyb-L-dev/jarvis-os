import { KnowledgeCenter } from "@/components/knowledge-center";

export default function KnowledgePage() {
  return (
    <main className="dashboard knowledge-page">
      <header className="topbar">
        <div>
          <div className="eyebrow">LOCAL KNOWLEDGE</div>
          <h1>
            Jarvis <span>知识库</span>
          </h1>
        </div>
      </header>
      <KnowledgeCenter />
    </main>
  );
}
