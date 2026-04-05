import * as React from 'react';

import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Send, X } from 'lucide-react';

import { Button, Textarea } from '../primitives';
import { cn } from '../utils';

import { AICoachSparkleIcon } from '../icons/AICoachSparkleIcon';
import type { CoachMessage, QuestionResult } from '../types';
import { ConversationMessage } from './ConversationMessage';

interface AICoachPanelProps {
  isOpen: boolean;
  isMobile: boolean;
  selectedQuestion: QuestionResult | null;
  needsReviewQuestions: QuestionResult[];
  allQuestions: QuestionResult[];
  messages: CoachMessage[];
  usedQuickPrompts: string[];
  isTyping: boolean;
  onClose: () => void;
  onSelectQuestion: (questionId: string) => void;
  onSubmitPrompt: (prompt: string) => Promise<void>;
  onMarkQuickPromptUsed: (prompt: string) => void;
}

const QUICK_PROMPTS = [
  'Why is this correct?',
  'Where did I go wrong?',
  'Give me a shortcut',
  'Step-by-step solution',
  'Test me on this',
];

function statusToken(question: QuestionResult | null) {
  if (!question) return 'No Question Selected';
  return question.status === 'correct' ? 'Correct' : 'Needs Review';
}

function statusBadgeClass(question: QuestionResult | null) {
  if (!question) return 'border-slate-300 bg-slate-100 text-slate-600';
  return question.status === 'correct'
    ? 'border-emerald-200 bg-emerald-100 text-emerald-700'
    : 'border-amber-200 bg-amber-100 text-amber-700';
}

export function AICoachPanel({
  isOpen,
  isMobile,
  selectedQuestion,
  needsReviewQuestions,
  allQuestions,
  messages,
  usedQuickPrompts,
  isTyping,
  onClose,
  onSelectQuestion,
  onSubmitPrompt,
  onMarkQuickPromptUsed,
}: AICoachPanelProps) {
  const [prompt, setPrompt] = React.useState('');
  const conversationRef = React.useRef<HTMLDivElement | null>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

  const switchableQuestions = needsReviewQuestions.length > 0 ? needsReviewQuestions : allQuestions;
  const quickPromptChoices = React.useMemo(() => {
    const remaining = QUICK_PROMPTS.filter((quickPrompt) => !usedQuickPrompts.includes(quickPrompt));
    return remaining.length > 0 ? remaining : QUICK_PROMPTS;
  }, [usedQuickPrompts]);
  const displayedSuggestions = quickPromptChoices.slice(0, 4);

  const submitPrompt = React.useCallback(
    async (value: string, markQuickPrompt = false) => {
      const normalized = value.trim();
      if (!normalized || !selectedQuestion) return;
      if (markQuickPrompt) onMarkQuickPromptUsed(normalized);
      setPrompt('');
      await onSubmitPrompt(normalized);
      if (textareaRef.current) textareaRef.current.style.height = '74px';
    },
    [onMarkQuickPromptUsed, onSubmitPrompt, selectedQuestion]
  );

  React.useEffect(() => {
    const node = conversationRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [messages, isTyping]);

  React.useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = '74px';
  }, [selectedQuestion?.id]);

  const panelBody = (
    <section
      role="complementary"
      aria-label="AI Coach"
      className="flex h-full min-h-0 flex-col bg-white"
    >
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-600">
              <AICoachSparkleIcon className="h-3.5 w-3.5 text-violet-600" />
              AI Coach
            </p>
            <h2 className="mt-0.5 text-sm font-semibold text-slate-900">Chat with AI Coach</h2>
            <p className="text-xs text-slate-500">Question-aware help, like a focused chat assistant.</p>
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={onClose} aria-label="Close AI Coach panel">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <select
              value={selectedQuestion?.id ?? ''}
              onChange={(event) => {
                var nextId = String(event.target.value || '').trim();
                if (nextId) onSelectQuestion(nextId);
              }}
              className="w-full appearance-none rounded-lg border border-slate-300 bg-white px-3 py-2.5 pr-8 text-xs font-medium text-slate-700 shadow-sm outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-200"
              aria-label="Select question for AI coach"
            >
              {!selectedQuestion ? <option value="">Select a question</option> : null}
              {switchableQuestions.map((question) => (
                <option key={question.id} value={question.id}>
                  {`Q${question.index} · ${question.topic}`}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          </div>

          <span
            className={cn(
              'inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold',
              statusBadgeClass(selectedQuestion)
            )}
          >
            {statusToken(selectedQuestion)}
          </span>
        </div>

        {selectedQuestion ? (
          <p className="mt-2 text-xs text-slate-500">{`Q${selectedQuestion.index} • ${selectedQuestion.topic}`}</p>
        ) : null}
      </header>

      <div
        ref={conversationRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-slate-50/70 px-4 py-4 talvo-scroll-zone"
      >
        {messages.length === 0 ? (
          <div className="mx-auto mt-10 max-w-sm text-center">
            <svg viewBox="0 0 48 48" className="mx-auto h-10 w-10 text-violet-500" fill="none" aria-hidden="true">
              <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
              <path d="M24 12l3.3 7.7L35 23l-7.7 3.3L24 34l-3.3-7.7L13 23l7.7-3.3L24 12z" fill="currentColor" opacity="0.9" />
            </svg>
            <p className="mt-3 text-sm font-semibold text-slate-800">Ask me about this question</p>
            <p className="mt-1 text-xs text-slate-500">Try an instant suggestion below or type your own follow-up.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => <ConversationMessage key={message.id} message={message} />)}
          </div>
        )}

        <AnimatePresence>
          {isTyping ? (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-3 py-1"
            >
              <span className="talvo-dot" />
              <span className="talvo-dot" />
              <span className="talvo-dot" />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <footer className="border-t border-slate-200 bg-white px-4 py-3">
        {selectedQuestion ? (
          <div className="mb-3">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500">Suggestions</p>
            <div className="grid grid-cols-2 gap-2">
              {displayedSuggestions.map((quickPrompt) => (
              <Button
                key={quickPrompt}
                type="button"
                size="sm"
                variant="outline"
                disabled={isTyping}
                className="h-auto min-h-10 justify-start rounded-xl border-slate-300 bg-slate-50 px-3 py-2 text-left text-xs font-medium leading-snug text-slate-700 whitespace-normal hover:bg-slate-100"
                onClick={() => {
                  void submitPrompt(quickPrompt, true);
                }}
              >
                {quickPrompt}
              </Button>
              ))}
            </div>
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submitPrompt(prompt);
          }}
        >
          <div className="relative overflow-hidden rounded-2xl border border-slate-300 bg-white shadow-sm">
            <Textarea
              ref={textareaRef}
              rows={1}
              value={prompt}
              onChange={(event) => {
                setPrompt(event.target.value);
                event.currentTarget.style.height = 'auto';
                const nextHeight = Math.max(40, Math.min(160, event.currentTarget.scrollHeight));
                event.currentTarget.style.height = `${nextHeight}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void submitPrompt(prompt);
                }
              }}
              className="min-h-[56px] max-h-40 resize-none rounded-none border-0 bg-transparent pr-12 text-sm focus-visible:ring-0"
              placeholder="Message AI Coach..."
            />

            <Button
              type="submit"
              size="icon"
              disabled={!selectedQuestion || !prompt.trim() || isTyping}
              className="absolute bottom-2 right-2 h-8 w-8 rounded-full bg-violet-600 hover:bg-violet-700"
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </form>

        <p className="mt-2 text-[11px] text-slate-500">Press Enter to send, Shift+Enter for a new line.</p>
      </footer>
    </section>
  );

  if (isMobile) {
    return (
      <AnimatePresence>
        {isOpen ? (
          <motion.aside
            key="coach-mobile-sheet"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
            className="fixed inset-x-0 bottom-0 z-40 h-[55vh] border-t border-slate-200 bg-slate-50 shadow-2xl"
          >
            {panelBody}
          </motion.aside>
        ) : null}
      </AnimatePresence>
    );
  }

  return panelBody;
}
