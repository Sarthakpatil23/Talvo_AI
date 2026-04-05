import * as React from 'react';

import { cn } from '../utils';

import type { CoachMessage } from '../types';

interface ConversationMessageProps {
  message: CoachMessage;
}

function splitByCodeFence(content: string): Array<{ type: 'text' | 'code'; value: string }> {
  const marker = '```';
  const chunks = content.split(marker);
  return chunks
    .map((value, index) => {
      const chunkType: 'text' | 'code' = index % 2 === 0 ? 'text' : 'code';
      return {
        type: chunkType,
        value: value.trim(),
      };
    })
    .filter((chunk) => chunk.value.length > 0);
}

function renderTextBlock(text: string, key: string) {
  const lines = text
    .split('\n')
    .map((line) => line.trimEnd())
    .filter((line) => line.length > 0);

  const numberedStepLines = lines.filter((line) => /^\d+[.)]\s+/.test(line));

  if (numberedStepLines.length >= 2) {
    return (
      <ol key={key} className="space-y-1 text-sm leading-7 text-slate-700 marker:text-violet-600 marker:font-semibold list-decimal pl-5">
        {lines.map((line, index) => (
          <li key={`${key}-${index}`}>{line.replace(/^\d+[.)]\s+/, '')}</li>
        ))}
      </ol>
    );
  }

  return (
    <p key={key} className="text-sm leading-7 text-slate-700 whitespace-pre-wrap">
      {text}
    </p>
  );
}

export function ConversationMessage({ message }: ConversationMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] rounded-[12px_12px_0_12px] bg-violet-600 px-3.5 py-2.5 text-sm leading-6 text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const chunks = splitByCodeFence(message.content);

  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-blue-600 text-[10px] font-bold text-white">
        AI
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        {chunks.length === 0 ? (
          <p className="text-sm leading-7 text-slate-700 whitespace-pre-wrap">{message.content}</p>
        ) : (
          chunks.map((chunk, index) => {
            const key = `${message.id}-${index}`;
            if (chunk.type === 'code') {
              return (
                <pre
                  key={key}
                  className={cn(
                    'overflow-x-auto rounded-md border border-slate-200 bg-slate-100 px-3 py-2',
                    'text-xs leading-6 text-slate-700 font-mono'
                  )}
                >
                  <code>{chunk.value}</code>
                </pre>
              );
            }
            return renderTextBlock(chunk.value, key);
          })
        )}
      </div>
    </div>
  );
}
