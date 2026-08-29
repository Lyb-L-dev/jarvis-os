import { LearningCoach } from "@/components/learning-coach";
import { LearningSchedule } from "@/components/learning-schedule";

export default function LearningPage() {
  return (
    <main className="dashboard learning-page">
      <header className="topbar">
        <div>
          <div className="eyebrow">LEARNING COACH · V5</div>
          <h1>
            学习<span>教练</span>
          </h1>
        </div>
      </header>
      <LearningSchedule />
      <LearningCoach />
    </main>
  );
}
