import * as React from 'react';
import { createRoot } from 'react-dom/client';

import { ResultsPage } from './components/ResultsPage';
import type { AskCoachPayload, CoachMessage, QuestionResult, ResultSummary } from './types';

interface DjangoReviewItem {
  id: string;
  category: string;
  question: string;
  selected_option: string;
  answer_option: string;
  is_correct: boolean;
}

interface DjangoResultsPayload {
  company_name: string;
  company_logo_url?: string;
  summary: {
    score: number;
    total_questions: number;
    percentage: number;
    duration_seconds: number;
  };
  review: DjangoReviewItem[];
  urls: {
    retake: string;
    resources: string;
    workspace: string;
    coach_api: string;
  };
}

function getCookie(name: string) {
  var key = `${name}=`;
  var chunks = document.cookie.split(';');
  for (var index = 0; index < chunks.length; index += 1) {
    var cookie = chunks[index].trim();
    if (cookie.indexOf(key) === 0) {
      return decodeURIComponent(cookie.slice(key.length));
    }
  }
  return '';
}

function parsePayload(): DjangoResultsPayload | null {
  var node = document.getElementById('aptitudeResultsPayload');
  if (!node) return null;

  try {
    return JSON.parse(node.textContent || '{}') as DjangoResultsPayload;
  } catch (error) {
    return null;
  }
}

function mapSummary(payload: DjangoResultsPayload): ResultSummary {
  return {
    score: Number(payload.summary?.score || 0),
    totalQuestions: Number(payload.summary?.total_questions || 0),
    percentage: Number(payload.summary?.percentage || 0),
    durationSeconds: Number(payload.summary?.duration_seconds || 0),
  };
}

function mapQuestions(payload: DjangoResultsPayload): QuestionResult[] {
  var review = Array.isArray(payload.review) ? payload.review : [];
  return review.map((item, index) => ({
    id: String(item.id || `q_${index + 1}`),
    index: index + 1,
    topic: String(item.category || 'Aptitude'),
    questionText: String(item.question || ''),
    userAnswer: String(item.selected_option || 'Not attempted'),
    correctAnswer: String(item.answer_option || ''),
    status: item.is_correct ? 'correct' : 'needs_review',
  }));
}

async function callCoachApi(payload: DjangoResultsPayload, askPayload: AskCoachPayload): Promise<string> {
  var response = await fetch(payload.urls.coach_api, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify({
      company: askPayload.companyName,
      question: {
        id: askPayload.question.id,
        question: askPayload.question.questionText,
        category: askPayload.question.topic,
        selected_option: askPayload.question.userAnswer,
        answer_option: askPayload.question.correctAnswer,
        is_correct: askPayload.question.status === 'correct',
      },
      prompt: askPayload.prompt,
      history: askPayload.history
        .slice(-10)
        .map((message: CoachMessage) => ({ role: message.role === 'assistant' ? 'assistant' : 'user', content: message.content })),
    }),
  });

  var data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error((data && data.error) || 'Coach request failed');
  }
  return String(data.answer || 'No answer returned.');
}

function mountAptitudeResults() {
  var mountNode = document.getElementById('aptitudeResultsReactRoot');
  var payload = parsePayload();
  if (!mountNode || !payload) return;

  var questions = mapQuestions(payload);
  var summary = mapSummary(payload);

  var root = createRoot(mountNode);
  root.render(
    <ResultsPage
      sidebarWidth={0}
      companyName={payload.company_name}
      companyLogoUrl={payload.company_logo_url || ''}
      summary={summary}
      questions={questions}
      onRetake={() => {
        window.location.href = payload.urls.retake;
      }}
      onGoResources={() => {
        window.location.href = payload.urls.resources;
      }}
      onBackToWorkspace={() => {
        window.location.href = payload.urls.workspace;
      }}
      onAskCoach={(askPayload) => callCoachApi(payload, askPayload)}
    />
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountAptitudeResults);
} else {
  mountAptitudeResults();
}
