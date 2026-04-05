import * as React from 'react';

import { motion } from 'framer-motion';
import { ArrowLeft, ChevronRight, Clock } from 'lucide-react';

import { Button, Card } from '../primitives';

interface ScoreHeaderProps {
  companyName: string;
  companyLogoUrl?: string;
  totalQuestions: number;
  score: number;
  percentage: number;
  durationSeconds: number;
  onRetake: () => void;
  onGoResources: () => void;
  onBackToWorkspace: () => void;
}

function arcColor(percentage: number) {
  if (percentage < 40) return '#EF4444';
  if (percentage < 75) return '#F59E0B';
  return '#22C55E';
}

function formatDuration(durationSeconds: number) {
  if (durationSeconds < 60) return `${durationSeconds}s`;
  const minutes = Math.floor(durationSeconds / 60);
  const seconds = durationSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function ScoreArc({ percentage }: { percentage: number }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, percentage));
  const targetOffset = circumference - (clamped / 100) * circumference;

  return (
    <svg viewBox="0 0 72 72" className="h-[72px] w-[72px]">
      <circle cx="36" cy="36" r={radius} stroke="rgba(255,255,255,0.24)" strokeWidth="4" fill="none" />
      <motion.circle
        cx="36"
        cy="36"
        r={radius}
        stroke={arcColor(percentage)}
        strokeWidth="4"
        strokeLinecap="round"
        fill="none"
        initial={{ strokeDasharray: circumference, strokeDashoffset: circumference }}
        animate={{ strokeDasharray: circumference, strokeDashoffset: targetOffset }}
        transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
        transform="rotate(-90 36 36)"
      />
    </svg>
  );
}

export function ScoreHeader({
  companyName,
  companyLogoUrl,
  totalQuestions,
  score,
  percentage,
  durationSeconds,
  onRetake,
  onGoResources,
  onBackToWorkspace,
}: ScoreHeaderProps) {
  return (
    <header className="relative overflow-hidden bg-gradient-to-br from-[#1E3A5F] to-[#0F2744] px-8 py-8 text-white md:px-10">
      <svg
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        aria-hidden="true"
        width="100%"
        height="100%"
      >
        <defs>
          <pattern id="talvo-grid-pattern" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="white" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#talvo-grid-pattern)" />
      </svg>

      <div className="relative z-10 grid gap-6 xl:grid-cols-[1fr_auto] xl:items-start">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">
            <span>Placement Hub</span>
            <ChevronRight className="h-3.5 w-3.5" />
            <span>Aptitude Round</span>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button variant="ghost" className="h-8 rounded-full border border-white/20 bg-white/10 px-3 text-xs font-semibold text-white hover:bg-white/20" onClick={onBackToWorkspace}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Back
            </Button>

            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white">
              {companyLogoUrl ? (
                <img src={companyLogoUrl} alt={`${companyName} logo`} className="h-4 w-4 rounded object-contain bg-white p-[1px]" />
              ) : null}
              <span>{companyName}</span>
              <span className="text-white/60">•</span>
              <span>{totalQuestions} Questions</span>
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Card className="border-white/20 bg-white/10 px-4 py-3 text-white shadow-none backdrop-blur">
            <p className="text-[11px] uppercase tracking-[0.12em] text-white/70">Score</p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <p className="text-3xl font-bold leading-none">{score}/{totalQuestions}</p>
              <ScoreArc percentage={percentage} />
            </div>
          </Card>

          <Card className="border-white/20 bg-white/10 px-4 py-3 text-white shadow-none backdrop-blur">
            <p className="text-[11px] uppercase tracking-[0.12em] text-white/70">Percentage</p>
            <p className="mt-3 text-3xl font-bold leading-none" style={{ color: arcColor(percentage) }}>
              {percentage}%
            </p>
          </Card>

          <Card className="border-white/20 bg-white/10 px-4 py-3 text-white shadow-none backdrop-blur">
            <p className="text-[11px] uppercase tracking-[0.12em] text-white/70">Time</p>
            <p className="mt-3 inline-flex items-center gap-2 text-2xl font-bold leading-none">
              <Clock className="h-4.5 w-4.5 text-white/80" />
              {formatDuration(durationSeconds)}
            </p>
          </Card>
        </div>
      </div>

      <div className="relative z-10 mt-5 flex flex-wrap gap-2.5">
        <Button className="bg-violet-600 text-white hover:bg-violet-700" onClick={onRetake}>
          Retake Aptitude
        </Button>
        <Button variant="outline" className="border-white/35 bg-transparent text-white hover:bg-white/10" onClick={onGoResources}>
          Go to Resources
        </Button>
        <Button variant="ghost" className="text-white/90 hover:bg-white/10" onClick={onBackToWorkspace}>
          Back to Company Workspace
        </Button>
      </div>
    </header>
  );
}
