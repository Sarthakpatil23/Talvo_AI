import * as React from 'react';

import { CheckCircle2, Sparkles, XCircle } from 'lucide-react';

import { Badge, Button, Card } from '../primitives';
import { cn } from '../utils';

import type { QuestionResult } from '../types';

interface QuestionCardProps {
  question: QuestionResult;
  activeForCoach: boolean;
  onAskCoach: (questionId: string) => void;
}

const TOPIC_STYLES: Array<{ matcher: RegExp; className: string }> = [
  { matcher: /data\s*interpretation/i, className: 'border-blue-200 bg-blue-50 text-blue-700' },
  { matcher: /quant/i, className: 'border-orange-200 bg-orange-50 text-orange-700' },
  { matcher: /logical/i, className: 'border-violet-200 bg-violet-50 text-violet-700' },
  { matcher: /verbal/i, className: 'border-teal-200 bg-teal-50 text-teal-700' },
];

function topicBadgeClass(topic: string) {
  const matched = TOPIC_STYLES.find((item) => item.matcher.test(topic));
  return matched?.className ?? 'border-slate-200 bg-slate-50 text-slate-700';
}

export function QuestionCard({ question, activeForCoach, onAskCoach }: QuestionCardProps) {
  const statusIsCorrect = question.status === 'correct';

  return (
    <Card
      role="article"
      aria-label={`Question ${question.index}`}
      className={cn(
        'mb-3 rounded-xl border border-slate-200 bg-white px-6 py-5 shadow-sm',
        'border-l-4',
        statusIsCorrect ? 'border-l-emerald-500' : 'border-l-rose-500',
        activeForCoach && !statusIsCorrect && 'border-l-violet-600 ring-1 ring-violet-200'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <Badge variant="outline" className={cn('font-semibold', topicBadgeClass(question.topic))}>
          {question.topic}
        </Badge>

        {statusIsCorrect ? (
          <Badge className="gap-1 bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Correct
          </Badge>
        ) : (
          <Badge className="gap-1 bg-rose-100 text-rose-700 hover:bg-rose-100">
            <XCircle className="h-3.5 w-3.5" />
            Needs Review
          </Badge>
        )}
      </div>

      <p className="mt-3 text-[15px] leading-relaxed text-slate-900">
        <span className="mr-1.5 font-bold text-violet-700">Q{question.index}.</span>
        <span className="font-medium">{question.questionText}</span>
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-start">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Your answer</p>
          <p
            className={cn(
              'mt-1 text-sm',
              statusIsCorrect ? 'font-semibold text-emerald-700' : 'text-rose-600 line-through decoration-rose-300'
            )}
          >
            {question.userAnswer}
          </p>
        </div>

        <div className="hidden h-full w-px bg-slate-200 md:block" aria-hidden="true" />

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Correct answer</p>
          <p className="mt-1 text-sm font-semibold text-emerald-700">{question.correctAnswer}</p>
        </div>
      </div>

      {!statusIsCorrect ? (
        <div className="mt-4 flex justify-end">
          <Button
            size="sm"
            variant={activeForCoach ? 'default' : 'outline'}
            className={cn(activeForCoach && 'bg-violet-600 text-white hover:bg-violet-700')}
            onClick={() => onAskCoach(question.id)}
          >
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            Ask AI Coach
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
