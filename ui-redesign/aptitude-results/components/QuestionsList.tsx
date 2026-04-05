import * as React from 'react';

import { motion } from 'framer-motion';

import type { QuestionResult } from '../types';
import { QuestionCard } from './QuestionCard';

interface QuestionsListProps {
  questions: QuestionResult[];
  selectedQuestionId: string | null;
  onAskCoach: (questionId: string) => void;
}

const listVariants = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.02,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.25,
      ease: [0.22, 1, 0.36, 1] as const,
    },
  },
};

export function QuestionsList({ questions, selectedQuestionId, onAskCoach }: QuestionsListProps) {
  return (
    <motion.div role="feed" aria-label="Aptitude question results" variants={listVariants} initial="hidden" animate="show">
      {questions.map((question) => (
        <motion.div key={question.id} variants={itemVariants}>
          <QuestionCard
            question={question}
            activeForCoach={selectedQuestionId === question.id}
            onAskCoach={onAskCoach}
          />
        </motion.div>
      ))}
    </motion.div>
  );
}
