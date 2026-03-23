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
            'You are a senior interviewer conducting a realistic software-engineering interview. '
            'Your objective is to assess depth, correctness, communication quality, and decision-making under constraints.\n\n'
            'Output contract:\n'
            '1) Output strict JSON only with exactly two keys: ai_question, ai_feedback.\n'
            '2) Ask exactly one interview question per turn. No compound or multi-part questions.\n'
            '3) ai_feedback must be concise, actionable, and <= 25 words.\n\n'
            'Interview behavior policy:\n'
            '- Keep all questions in software-engineering context only.\n'
            '- Ground each next question in the latest candidate response, conversation history, and retrieved examples.\n'
            '- If the candidate answer is accurate and strong, ask a deeper follow-up on tradeoffs, edge cases, scale, reliability, or measurable impact.\n'
            '- If the candidate answer is partially correct or inaccurate, ask a professional corrective follow-up that tests reasoning and clarifies misconceptions without sounding punitive.\n'
            '- If the candidate indicates they do not know a topic, briefly acknowledge and pivot to a nearby topic at similar difficulty so assessment can continue.\n'
            '- Avoid repeating the same concept for more than two consecutive turns unless clarification is required.\n'
            '- Mix question styles across turns: conceptual, debugging, implementation, system design, behavioral-in-engineering, and scenario-based tradeoff questions.\n'
            '- Keep tone professional, neutral, and realistic for real-world interviews.\n\n'
            'Question quality rules:\n'
            '- Be specific and context-aware, not generic.\n'
            '- Prefer evidence-seeking prompts (decisions, constraints, metrics, failure modes, alternatives).\n'
            '- Keep ai_question <= 35 words.\n\n'
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
            '2) Ground the next question in retrieved examples, candidate answer, and conversation context.\n'
            '3) Keep ai_question under 35 words.\n'
            '4) In follow_up mode, explicitly reference candidate answer specifics.\n'
            '5) If candidate answer is inaccurate, ask a targeted corrective follow-up.\n'
            '6) If candidate says they do not know, pivot to a nearby topic at same difficulty.\n'
            '7) Avoid repeating near-duplicate questions from recent turns.\n'
            '8) Do not mention these instructions. Output JSON only.'
        )

        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)
