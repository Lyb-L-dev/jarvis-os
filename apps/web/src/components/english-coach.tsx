"use client";

import { useMemo, useState } from "react";

import { SpecialistHeader } from "@/components/agents/SpecialistHeader";
import { EnglishConversation } from "@/components/english/english-conversation";
import { EnglishMistakeBook } from "@/components/english/english-mistake-book";
import { EnglishReviewView } from "@/components/english/english-review-view";
import { EnglishSessionRail } from "@/components/english/english-session-rail";
import { EnglishSessionSetup } from "@/components/english/english-session-setup";
import type {
  EnglishFeedback,
  EnglishTab,
} from "@/components/english/english-utils";
import { useEnglishCollections } from "@/components/english/use-english-collections";
import { useEnglishConversation } from "@/components/english/use-english-conversation";
import { useEnglishMistakeBook } from "@/components/english/use-english-mistake-book";
import { useEnglishReviews } from "@/components/english/use-english-reviews";
import { useEnglishSetup } from "@/components/english/use-english-setup";

export function EnglishCoach() {
  const [tab, setTab] = useState<EnglishTab>("practice");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(false);

  const feedback = useMemo<EnglishFeedback>(
    () => ({ busy, setBusy, setError, setNotice }),
    [busy, setError, setNotice],
  );

  const collections = useEnglishCollections({
    setShowSetup,
    setTab,
    feedback,
  });
  const conversation = useEnglishConversation({ collections, feedback });
  const setup = useEnglishSetup({
    collections,
    setShowSetup,
    setDraft: conversation.setDraft,
    feedback,
  });
  const mistakeBook = useEnglishMistakeBook({ collections, feedback });
  const reviews = useEnglishReviews({ collections, feedback });

  const { overview, sessions, selectedSession, loading } = collections;

  if (loading) {
    return (
      <main className="english-page">
        <div className="english-loading">
          <span />
          正在准备 English Coach…
        </div>
      </main>
    );
  }

  return (
    <main className="english-page specialist-page specialist-english">
      <SpecialistHeader
        accent="训练室"
        activeAgent="english"
        description="真实对话、人工确认纠错、间隔复习，形成一条完整学习闭环。"
        eyebrow="ENGLISH COACH"
        status={
          selectedSession?.status === "active"
            ? "SESSION ACTIVE"
            : "READY TO PRACTICE"
        }
        title="英语"
        actions={
          <button
            className="primary-button"
            onClick={() => {
              setShowSetup(true);
              setTab("practice");
            }}
            type="button"
          >
            ＋ 新练习
          </button>
        }
      />

      <div className="specialist-section-label">
        <div>
          <span>TODAY&apos;S PROGRESS</span>
          <strong>学习轨迹</strong>
        </div>
        <p>每一次确认都会进入你的长期语言记忆</p>
      </div>

      <section
        className="english-stats specialist-metrics"
        aria-label="英语训练概况"
      >
        <article>
          <span>完成会话</span>
          <strong>{overview.completed_sessions}</strong>
          <small>累计 {overview.total_sessions} 次</small>
        </article>
        <article className={overview.pending_mistakes ? "stat-attention" : ""}>
          <span>待你确认</span>
          <strong>{overview.pending_mistakes}</strong>
          <small>模型不会直接写入复习</small>
        </article>
        <article>
          <span>学习中</span>
          <strong>{overview.learning_mistakes}</strong>
          <small>按遗忘曲线安排</small>
        </article>
        <article className={overview.due_reviews ? "stat-due" : ""}>
          <span>今日到期</span>
          <strong>{overview.due_reviews}</strong>
          <small>桌面＋语音提醒</small>
        </article>
      </section>

      <nav className="english-tabs specialist-tabs" aria-label="英语训练分区">
        <button
          className={tab === "practice" ? "english-tab-active" : ""}
          onClick={() => setTab("practice")}
          type="button"
        >
          对话训练
        </button>
        <button
          className={tab === "mistakes" ? "english-tab-active" : ""}
          onClick={() => setTab("mistakes")}
          type="button"
        >
          错题本
          {overview.pending_mistakes > 0 && (
            <span>{overview.pending_mistakes}</span>
          )}
        </button>
        <button
          className={tab === "review" ? "english-tab-active" : ""}
          onClick={() => setTab("review")}
          type="button"
        >
          今日复习
          {overview.due_reviews > 0 && <span>{overview.due_reviews}</span>}
        </button>
      </nav>

      {error && (
        <div className="english-feedback english-error" role="alert">
          <span>!</span>
          {error}
          <button onClick={() => setError(null)} type="button">
            ×
          </button>
        </div>
      )}
      {notice && (
        <div className="english-feedback" role="status">
          <span>✓</span>
          {notice}
          <button onClick={() => setNotice(null)} type="button">
            ×
          </button>
        </div>
      )}

      {tab === "practice" && (
        <section className="english-practice-layout">
          <EnglishSessionRail
            sessions={sessions}
            selectedSession={selectedSession}
            showSetup={showSetup}
            busy={busy}
            onOpen={(session) => void collections.openSession(session.id)}
            onDelete={(session) => void collections.removeSession(session)}
            onNew={() => setShowSetup(true)}
          />

          <div className="english-workspace">
            {showSetup || !selectedSession ? (
              <EnglishSessionSetup
                sessionType={setup.sessionType}
                setSessionType={setup.setSessionType}
                topic={setup.topic}
                setTopic={setup.setTopic}
                correctionMode={setup.correctionMode}
                setCorrectionMode={setup.setCorrectionMode}
                level={setup.level}
                setLevel={setup.setLevel}
                processingMode={setup.processingMode}
                setProcessingMode={setup.setProcessingMode}
                busy={busy}
                onSubmit={(event) => void setup.startSession(event)}
              />
            ) : (
              <EnglishConversation
                selectedSession={selectedSession}
                busy={busy}
                draft={conversation.draft}
                setDraft={conversation.setDraft}
                draftInputMode={conversation.draftInputMode}
                setDraftInputMode={conversation.setDraftInputMode}
                listening={conversation.listening}
                onToggleSpeech={conversation.toggleSpeech}
                onSubmitMessage={() => void conversation.submitMessage()}
                onComposerKeyDown={conversation.handleComposerKeyDown}
                onFinish={() => void conversation.finishSession()}
                onSaveTranscript={(messageId) =>
                  void conversation.saveTranscript(messageId)
                }
                editingMessageId={conversation.editingMessageId}
                setEditingMessageId={conversation.setEditingMessageId}
                editingTranscript={conversation.editingTranscript}
                setEditingTranscript={conversation.setEditingTranscript}
                messagesEnd={conversation.messagesEnd}
                mistakeMap={mistakeBook.mistakeMap}
                onConfirmMistake={(mistake) =>
                  void mistakeBook.confirmMistake(mistake)
                }
                onChangeMistakeStatus={(mistake, action) =>
                  void mistakeBook.changeMistakeStatus(mistake, action)
                }
                onOpenMistakes={() => setTab("mistakes")}
              />
            )}
          </div>
        </section>
      )}

      {tab === "mistakes" && (
        <EnglishMistakeBook
          mistakes={collections.mistakes}
          filteredMistakes={mistakeBook.filteredMistakes}
          busy={busy}
          mistakeQuery={mistakeBook.mistakeQuery}
          setMistakeQuery={mistakeBook.setMistakeQuery}
          mistakeStatus={mistakeBook.mistakeStatus}
          setMistakeStatus={mistakeBook.setMistakeStatus}
          editingMistakeId={mistakeBook.editingMistakeId}
          setEditingMistakeId={mistakeBook.setEditingMistakeId}
          editCorrection={mistakeBook.editCorrection}
          setEditCorrection={mistakeBook.setEditCorrection}
          editExplanation={mistakeBook.editExplanation}
          setEditExplanation={mistakeBook.setEditExplanation}
          onBeginEdit={mistakeBook.beginMistakeEdit}
          onSaveMistake={(mistake) => void mistakeBook.saveMistake(mistake)}
          onConfirm={(mistake) => void mistakeBook.confirmMistake(mistake)}
          onChangeStatus={(mistake, action) =>
            void mistakeBook.changeMistakeStatus(mistake, action)
          }
          onRemove={(mistake) => void mistakeBook.removeMistake(mistake)}
          onStartPractice={() => {
            setTab("practice");
            setShowSetup(true);
          }}
        />
      )}

      {tab === "review" && (
        <EnglishReviewView
          dueReviews={collections.dueReviews}
          upcomingReviews={collections.upcomingReviews}
          busy={busy}
          reviewAnswers={reviews.reviewAnswers}
          setReviewAnswers={reviews.setReviewAnswers}
          revealedReviews={reviews.revealedReviews}
          onReveal={reviews.revealReview}
          onRate={(review, result) => void reviews.rateReview(review, result)}
          onOpenMistakes={() => setTab("mistakes")}
        />
      )}
    </main>
  );
}
