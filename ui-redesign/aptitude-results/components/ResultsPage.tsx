import * as React from 'react';

import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

import { Button } from '../primitives';
import { cn } from '../utils';

import type { AskCoachHandler, CoachMessage, QuestionResult, ResultSummary } from '../types';
import { AICoachPanel } from './AICoachPanel';
import { QuestionsList } from './QuestionsList';
import { ScoreHeader } from './ScoreHeader';

interface ResultsPageProps {
  sidebar?: React.ReactNode;
  sidebarWidth?: number;
  companyName: string;
  companyLogoUrl?: string;
  summary: ResultSummary;
  questions: QuestionResult[];
  onRetake: () => void;
  onGoResources: () => void;
  onBackToWorkspace: () => void;
  onAskCoach?: AskCoachHandler;
}

function useIsMobile(breakpoint = 1023) {
  const [mobile, setMobile] = React.useState(false);

  React.useEffect(() => {
    const query = window.matchMedia(`(max-width: ${breakpoint}px)`);
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, [breakpoint]);

  return mobile;
}

function fallbackCoachAnswer(question: QuestionResult, prompt: string) {
  const isCorrect = question.status === 'correct';

  if (isCorrect) {
    return [
      'Your selected answer is correct.',
      'Reasoning: check the key condition in the question first, then validate with one sanity check.',
      `If you want, I can give a faster method specifically for: ${prompt}`,
    ].join('\n');
  }

  return [
    `You missed this one. The correct answer is: ${question.correctAnswer}.`,
    'Likely issue: either concept mismatch, elimination mistake, or arithmetic slip.',
    'Try this flow: identify concept → estimate rough range → solve once → verify units/logic.',
  ].join('\n');
}

function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}_${Date.now().toString(36)}`;
}

export function ResultsPage({
  sidebar,
  sidebarWidth = 220,
  companyName,
  companyLogoUrl,
  summary,
  questions,
  onRetake,
  onGoResources,
  onBackToWorkspace,
  onAskCoach,
}: ResultsPageProps) {
  const isMobile = useIsMobile();
  const needsReviewQuestions = React.useMemo(
    () => questions.filter((question) => question.status === 'needs_review'),
    [questions]
  );

  const defaultQuestion = needsReviewQuestions[0] ?? questions[0] ?? null;

  const [isCoachOpen, setCoachOpen] = React.useState(false);
  const [selectedQuestionId, setSelectedQuestionId] = React.useState<string | null>(defaultQuestion?.id ?? null);
  const [typingQuestionId, setTypingQuestionId] = React.useState<string | null>(null);
  const [messagesByQuestion, setMessagesByQuestion] = React.useState<Record<string, CoachMessage[]>>({});
  const [usedQuickPromptsByQuestion, setUsedQuickPromptsByQuestion] = React.useState<Record<string, string[]>>({});

  React.useEffect(() => {
    if (!selectedQuestionId && defaultQuestion) {
      setSelectedQuestionId(defaultQuestion.id);
    }
  }, [defaultQuestion, selectedQuestionId]);

  const selectedQuestion = React.useMemo(
    () => questions.find((question) => question.id === selectedQuestionId) ?? null,
    [questions, selectedQuestionId]
  );

  const selectedMessages = selectedQuestionId ? messagesByQuestion[selectedQuestionId] ?? [] : [];
  const usedQuickPrompts = selectedQuestionId ? usedQuickPromptsByQuestion[selectedQuestionId] ?? [] : [];

  async function submitPrompt(prompt: string) {
    if (!selectedQuestion) return;

    const userMessage: CoachMessage = {
      id: uid('user'),
      role: 'user',
      content: prompt,
      createdAt: Date.now(),
    };

    setMessagesByQuestion((previous) => {
      const existing = previous[selectedQuestion.id] ?? [];
      return { ...previous, [selectedQuestion.id]: [...existing, userMessage] };
    });

    setTypingQuestionId(selectedQuestion.id);

    try {
      const history = [...(messagesByQuestion[selectedQuestion.id] ?? []), userMessage].slice(-12);
      const answer = onAskCoach
        ? await onAskCoach({
            companyName,
            question: selectedQuestion,
            prompt,
            history,
          })
        : fallbackCoachAnswer(selectedQuestion, prompt);

      const assistantMessage: CoachMessage = {
        id: uid('assistant'),
        role: 'assistant',
        content: answer,
        createdAt: Date.now(),
      };

      setMessagesByQuestion((previous) => {
        const existing = previous[selectedQuestion.id] ?? [];
        return { ...previous, [selectedQuestion.id]: [...existing, assistantMessage] };
      });
    } catch (error) {
      const assistantMessage: CoachMessage = {
        id: uid('assistant'),
        role: 'assistant',
        content: [
          'I could not reach the live AI coach right now.',
          'Here is a quick fallback explanation while you retry:',
          fallbackCoachAnswer(selectedQuestion, prompt),
        ].join('\n\n'),
        createdAt: Date.now(),
      };

      setMessagesByQuestion((previous) => {
        const existing = previous[selectedQuestion.id] ?? [];
        return { ...previous, [selectedQuestion.id]: [...existing, assistantMessage] };
      });
    } finally {
      setTypingQuestionId(null);
    }
  }

  const hasSidebar = Boolean(sidebar) && sidebarWidth > 0;

  const gridTemplateColumns = isMobile
    ? hasSidebar
      ? `${sidebarWidth}px minmax(0, 1fr)`
      : 'minmax(0, 1fr)'
    : hasSidebar
      ? (isCoachOpen ? `${sidebarWidth}px minmax(0, 1fr) 420px` : `${sidebarWidth}px minmax(0, 1fr) 0px`)
      : (isCoachOpen ? 'minmax(0, 1fr) 420px' : 'minmax(0, 1fr) 0px');

  return (
    <motion.main
      layout
      className="h-screen overflow-hidden bg-slate-50 text-slate-900"
      style={{
        display: 'grid',
        gridTemplateRows: 'auto minmax(0, 1fr)',
        gridTemplateColumns,
        transition: 'grid-template-columns 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      <style>{`
        .talvo-scroll-zone {
          scrollbar-width: thin;
          scrollbar-color: rgba(108, 71, 255, 0.3) transparent;
        }
        .talvo-scroll-zone::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .talvo-scroll-zone::-webkit-scrollbar-thumb {
          background: rgba(108, 71, 255, 0.32);
          border-radius: 999px;
        }
        .talvo-scroll-zone::-webkit-scrollbar-track {
          background: transparent;
        }
        .talvo-dot {
          width: 6px;
          height: 6px;
          border-radius: 999px;
          background: #6366f1;
          display: inline-block;
          animation: talvoDotBounce 900ms infinite ease-in-out;
        }
        .talvo-dot:nth-child(2) { animation-delay: 100ms; }
        .talvo-dot:nth-child(3) { animation-delay: 200ms; }

        @keyframes talvoDotBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
          40% { transform: translateY(-3px); opacity: 1; }
        }
      `}</style>

      <div style={{ gridColumn: '1 / -1' }}>
        <ScoreHeader
          companyName={companyName}
          companyLogoUrl={companyLogoUrl}
          totalQuestions={summary.totalQuestions}
          score={summary.score}
          percentage={summary.percentage}
          durationSeconds={summary.durationSeconds}
          onRetake={onRetake}
          onGoResources={onGoResources}
          onBackToWorkspace={onBackToWorkspace}
        />
      </div>

      {hasSidebar ? <aside className="min-h-0 overflow-hidden border-r border-slate-200">{sidebar}</aside> : null}

      <section
        className={cn(
          'min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain px-6 py-5 talvo-scroll-zone md:px-8',
          isMobile && isCoachOpen && 'pb-[57vh]'
        )}
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Question Review</h2>
            <p className="text-sm text-slate-500">Scannable breakdown of every question with answer comparisons.</p>
          </div>

          <Button
            variant={isCoachOpen ? 'default' : 'outline'}
            className={cn(
              'rounded-full',
              isCoachOpen && 'bg-violet-600 text-white hover:bg-violet-700'
            )}
            onClick={() => setCoachOpen((value) => !value)}
          >
            <Sparkles className="mr-1.5 h-4 w-4" />
            {isCoachOpen ? 'Hide AI Coach' : 'Open AI Coach'}
          </Button>
        </div>

        <QuestionsList
          questions={questions}
          selectedQuestionId={selectedQuestionId}
          onAskCoach={(questionId) => {
            setSelectedQuestionId(questionId);
            setCoachOpen(true);
          }}
        />
      </section>

      {!isMobile ? (
        <motion.aside
          initial={false}
          animate={{ x: isCoachOpen ? 0 : 420 }}
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
          className={cn(
            'min-h-0 h-full overflow-hidden border-l border-slate-200 bg-slate-50',
            !isCoachOpen && 'pointer-events-none'
          )}
        >
          <AICoachPanel
            isOpen={isCoachOpen}
            isMobile={false}
            selectedQuestion={selectedQuestion}
            needsReviewQuestions={needsReviewQuestions}
            allQuestions={questions}
            messages={selectedMessages}
            usedQuickPrompts={usedQuickPrompts}
            isTyping={typingQuestionId === selectedQuestionId}
            onClose={() => setCoachOpen(false)}
            onSelectQuestion={(questionId) => {
              setSelectedQuestionId(questionId);
              setCoachOpen(true);
            }}
            onSubmitPrompt={submitPrompt}
            onMarkQuickPromptUsed={(prompt) => {
              if (!selectedQuestionId) return;
              setUsedQuickPromptsByQuestion((previous) => {
                const existing = previous[selectedQuestionId] ?? [];
                if (existing.includes(prompt)) return previous;
                return { ...previous, [selectedQuestionId]: [...existing, prompt] };
              });
            }}
          />
        </motion.aside>
      ) : (
        <AICoachPanel
          isOpen={isCoachOpen}
          isMobile
          selectedQuestion={selectedQuestion}
          needsReviewQuestions={needsReviewQuestions}
          allQuestions={questions}
          messages={selectedMessages}
          usedQuickPrompts={usedQuickPrompts}
          isTyping={typingQuestionId === selectedQuestionId}
          onClose={() => setCoachOpen(false)}
          onSelectQuestion={(questionId) => {
            setSelectedQuestionId(questionId);
            setCoachOpen(true);
          }}
          onSubmitPrompt={submitPrompt}
          onMarkQuickPromptUsed={(prompt) => {
            if (!selectedQuestionId) return;
            setUsedQuickPromptsByQuestion((previous) => {
              const existing = previous[selectedQuestionId] ?? [];
              if (existing.includes(prompt)) return previous;
              return { ...previous, [selectedQuestionId]: [...existing, prompt] };
            });
          }}
        />
      )}
    </motion.main>
  );
}
