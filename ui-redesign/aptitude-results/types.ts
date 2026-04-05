export type QuestionStatus = 'correct' | 'needs_review';
export type CoachRole = 'user' | 'assistant';

export interface ResultSummary {
  score: number;
  totalQuestions: number;
  percentage: number;
  durationSeconds: number;
}

export interface QuestionResult {
  id: string;
  index: number;
  topic: string;
  questionText: string;
  userAnswer: string;
  correctAnswer: string;
  status: QuestionStatus;
}

export interface CoachMessage {
  id: string;
  role: CoachRole;
  content: string;
  createdAt: number;
}

export interface AskCoachPayload {
  companyName: string;
  question: QuestionResult;
  prompt: string;
  history: CoachMessage[];
}

export type AskCoachHandler = (payload: AskCoachPayload) => Promise<string>;
