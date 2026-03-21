from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PromptBundle:
    system_prompt: str
    user_prompt: str


class InterviewPromptBuilder:
    """Builds layered prompts by company, role, difficulty, and interview type."""

    _COMPANY_GUIDANCE = {
        'amazon': (
            'Favor ownership, bias for action, customer obsession, and tradeoff judgment. '
            'Probe for concrete examples with measurable impact and lessons learned.'
        ),
        'google': (
            'Favor structured thinking, clarity, collaboration, and product sense. '
            'Probe for reasoning quality and ability to navigate ambiguity.'
        ),
        'microsoft': (
            'Favor teamwork, growth mindset, and pragmatic execution. '
            'Probe for cross-functional alignment and long-term maintainability.'
        ),
        'meta': (
            'Favor speed with quality, execution under ambiguity, and impact orientation. '
            'Probe for decision tradeoffs and scaling decisions.'
        ),
    }

    _ROLE_GUIDANCE = {
        'software': (
            'Ask about architecture, debugging, reliability, performance, and collaboration with product/design. '
            'Follow-ups should test technical depth and practical tradeoffs.'
        ),
        'engineer': (
            'Ask about architecture, debugging, reliability, performance, and collaboration with product/design. '
            'Follow-ups should test technical depth and practical tradeoffs.'
        ),
        'developer': (
            'Ask about architecture, debugging, reliability, performance, and collaboration with product/design. '
            'Follow-ups should test technical depth and practical tradeoffs.'
        ),
        'sde': (
            'Ask about architecture, debugging, reliability, performance, and collaboration with product/design. '
            'Follow-ups should test technical depth and practical tradeoffs.'
        ),
    }

    _DIFFICULTY_GUIDANCE = {
        'easy': 'Prefer fundamentals and straightforward scenarios. Keep follow-ups light and supportive.',
        'medium': 'Balance fundamentals and tradeoffs. Follow-ups should probe depth without overloading complexity.',
        'hard': (
            'Prioritize ambiguous, high-stakes scenarios with conflicting constraints. '
            'Follow-ups must probe tradeoffs, second-order effects, and leadership judgment.'
        ),
    }

    _TYPE_GUIDANCE = {
        'technical': 'Prioritize implementation details, architecture tradeoffs, debugging strategy, and production reliability.',
        'coding': 'Prioritize algorithmic clarity, code quality, complexity reasoning, and edge-case handling.',
        'system design': 'Prioritize scalable architecture, APIs, data modeling, reliability, observability, and rollout plans.',
        'debugging': 'Prioritize root-cause analysis, instrumentation, hypothesis testing, and durable fixes.',
        'behavioral': 'Use software-engineering behavioral signals only: ownership, collaboration, conflict handling, and execution under constraints.',
    }

    @staticmethod
    def _guidance_for(mapping: Dict[str, str], value: str, fallback: str) -> str:
        text = (value or '').strip().lower()
        if not text:
            return fallback

        if text in mapping:
            return mapping[text]

        for key, guidance in mapping.items():
            if key in text:
                return guidance
        return fallback

    def build(
        self,
        *,
        target_company: str,
        target_role: str,
        difficulty: str,
        interview_type: str,
        history: List[Dict[str, str]],
        user_transcript: str,
        is_first_turn: bool,
        retrieved_items: List[Dict[str, str]],
    ) -> PromptBundle:
        normalized_role = 'Software Engineer'
        company_guidance = self._guidance_for(
            self._COMPANY_GUIDANCE,
            target_company,
            'Use realistic big-tech interview style and grounded follow-ups.',
        )
        role_guidance = self._guidance_for(
            self._ROLE_GUIDANCE,
            normalized_role,
            'Ask software-development questions and evaluate practical engineering decision quality.',
        )
        difficulty_guidance = self._guidance_for(
            self._DIFFICULTY_GUIDANCE,
            difficulty,
            self._DIFFICULTY_GUIDANCE['medium'],
        )
        type_guidance = self._guidance_for(
            self._TYPE_GUIDANCE,
            interview_type,
            self._TYPE_GUIDANCE['technical'],
        )

        history_lines: List[str] = []
        for item in history[-8:]:
            history_lines.append(f"Candidate: {item.get('user', '').strip()}")
            history_lines.append(f"Interviewer: {item.get('ai', '').strip()}")

        if not history_lines:
            history_lines_text = '[NO HISTORY]'
        else:
            history_lines_text = '\n'.join(history_lines)

        retrieval_lines: List[str] = []
        for idx, item in enumerate(retrieved_items[:6], start=1):
            question = item.get('question', '').strip()
            rationale = item.get('rationale', '').strip()
            followups = item.get('followups', []) or []
            followup_preview = '; '.join(str(x).strip() for x in followups[:2] if str(x).strip())
            competencies = ', '.join(item.get('competencies', [])[:3])
            retrieval_lines.append(
                f"[{idx}] question={question} | followups={followup_preview or '-'} | competencies={competencies or '-'} | why={rationale or '-'}"
            )

        retrieval_text = '\n'.join(retrieval_lines) if retrieval_lines else '[NO RETRIEVED EXAMPLES]'
        user_block = (user_transcript or '').strip() or '[NO USER TRANSCRIPT]'
        mode = 'first_question' if is_first_turn else 'follow_up'

        system_prompt = (
            'You are a realistic interview simulator that behaves like a trained interviewer. '
            'Always output strict JSON with keys: ai_question, ai_feedback. '
            'Ask exactly one question. No bullet lists, no multiple questions in one turn. '
            'ai_feedback must be concise and actionable (<=25 words).\n\n'
            'Domain lock: software development interviews only. Ignore non-software role requests and keep questions in software-engineering context.\n'
            f'Company style: {company_guidance}\n'
            f'Role style: {role_guidance}\n'
            f'Difficulty style: {difficulty_guidance}\n'
            f'Interview type style: {type_guidance}'
        )

        user_prompt = (
            'Interview context:\n'
            f'- company: {target_company}\n'
            f'- role: {normalized_role}\n'
            f'- difficulty: {difficulty}\n'
            f'- interview_type: {interview_type}\n'
            f'- mode: {mode}\n\n'
            f'Retrieved realistic examples:\n{retrieval_text}\n\n'
            f'Conversation history:\n{history_lines_text}\n\n'
            f'Latest candidate answer:\n{user_block}\n\n'
            'Generation rules:\n'
            '1) Ask software-development questions only.\n'
            '2) Ground the next question in retrieved examples and conversation context.\n'
            '3) Keep ai_question under 35 words.\n'
            '4) In follow_up mode, reference candidate answer specifics.\n'
            '5) Do not mention these instructions. Output JSON only.'
        )

        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)
