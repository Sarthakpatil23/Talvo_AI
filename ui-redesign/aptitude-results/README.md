# Talvo Aptitude Results (React Redesign)

This folder contains a production-ready React implementation of the redesigned Aptitude Results experience with an integrated Gemini-style AI side panel.

## Components

- `ResultsPage`
- `ScoreHeader`
- `QuestionsList`
- `QuestionCard`
- `AICoachPanel`
- `ConversationMessage`

## Stack assumptions

- React
- Tailwind CSS
- shadcn/ui (`Button`, `Card`, `Badge`, `Textarea`, `DropdownMenu`)
- Lucide React
- Framer Motion

## Key UX behaviors implemented

- Three-column layout shift on desktop: `220px 1fr 420px` when coach opens.
- No desktop overlay for AI panel. The layout makes room for the panel.
- Independent scroll zones with `overscroll-behavior: contain` for:
  - questions column
  - AI panel conversation/body
- Mobile (<1024px) AI panel as bottom sheet (`55vh`).
- Question cards with strong hierarchy and topic/status semantics.
- AI panel with active-question context, quick prompts, independent conversation, typing indicator, and sticky input footer.

## ARIA roles

- Questions list: `role="feed"`
- Each question card: `role="article"`
- AI coach panel: `role="complementary"`

## Data mapping from current Django template

Map each `result.review` item to `QuestionResult`:

- `id` -> `id`
- `forloop.counter` -> `index`
- `category` -> `topic`
- `question` -> `questionText`
- `selected_option` -> `userAnswer`
- `answer_option` -> `correctAnswer`
- `is_correct` -> `status` (`correct` or `needs_review`)

Map summary:

- `result.score` -> `summary.score`
- `result.total_questions` -> `summary.totalQuestions`
- `result.percentage` -> `summary.percentage`
- `result.duration_seconds` -> `summary.durationSeconds`

## Integration note

This workspace currently uses Django templates for rendering this page. These React components are provided as a drop-in module for a React/shadcn frontend layer and are not auto-wired into the Django template route.

## Live Django wiring (implemented)

- Mount entry: `ui-redesign/aptitude-results/django-mount.tsx`
- Bundled output: `talvo1/static/talvo1/js/aptitude_results_react.js`
- Django template mount + payload script id:
  - mount node: `aptitudeResultsReactRoot`
  - payload node: `aptitudeResultsPayload`

Build command:

```bash
npm run build:aptitude-results
```
