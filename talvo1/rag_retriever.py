import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List

from django.conf import settings


class InterviewRAGRetriever:
    """Phase-2 RAG retriever with metadata retrieval and MMR-style reranking."""

    _SOFTWARE_ROLE_HINTS = (
        'software',
        'developer',
        'engineer',
        'sde',
        'backend',
        'frontend',
        'fullstack',
        'full stack',
    )

    def __init__(self) -> None:
        self._dataset = self._load_dataset()
        self._token_idf = self._build_token_idf(self._dataset)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r'\s+', ' ', (text or '').strip().lower())

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        cleaned = re.sub(r'[^a-z0-9\s]', ' ', (text or '').lower())
        return [tok for tok in cleaned.split() if len(tok) > 2]

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        inter = len(a.intersection(b))
        union = len(a.union(b))
        return (inter / union) if union else 0.0

    def _build_token_idf(self, dataset: List[Dict[str, object]]) -> Dict[str, float]:
        df = Counter()
        for item in dataset:
            toks = set(self._tokenize(str(item.get('question', ''))))
            for f in item.get('followups', [])[:3]:
                toks.update(self._tokenize(str(f)))
            for t in item.get('tags', []):
                toks.update(self._tokenize(str(t)))
            for tok in toks:
                df[tok] += 1

        total_docs = max(1, len(dataset))
        idf: Dict[str, float] = {}
        for tok, freq in df.items():
            idf[tok] = math.log((1 + total_docs) / (1 + freq)) + 1.0
        return idf

    @staticmethod
    def _is_software_only_enabled() -> bool:
        return str(getattr(settings, 'INTERVIEW_SOFTWARE_ONLY', '1')).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _is_software_role(self, role: str) -> bool:
        normalized = self._normalize(role)
        if not normalized:
            return False
        return any(hint in normalized for hint in self._SOFTWARE_ROLE_HINTS)

    @staticmethod
    def _allowed_software_types() -> List[str]:
        raw = str(getattr(settings, 'INTERVIEW_SOFTWARE_ALLOWED_TYPES', 'technical,coding,system design,debugging,behavioral'))
        return [part.strip().lower() for part in raw.split(',') if part.strip()]

    def _normalize_software_type(self, interview_type: str) -> str:
        normalized = self._normalize(interview_type)
        allowed = self._allowed_software_types()
        if not allowed:
            return 'technical'
        if normalized in allowed:
            return normalized
        for candidate in allowed:
            if candidate in normalized or normalized in candidate:
                return candidate
        return 'technical'

    def _load_dataset(self) -> List[Dict[str, object]]:
        raw_path = getattr(settings, 'INTERVIEW_RAG_DATA_PATH', '')
        if raw_path:
            candidate = Path(raw_path)
            path = candidate if candidate.is_absolute() else Path(settings.BASE_DIR) / candidate
        else:
            path = Path(settings.BASE_DIR) / 'talvo1' / 'data' / 'interview_question_bank.json'
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return []

        if isinstance(payload, dict):
            items = payload.get('items', [])
        else:
            items = payload

        if not isinstance(items, list):
            return []

        valid: List[Dict[str, object]] = []
        for row in items:
            if not isinstance(row, dict):
                continue
            question = (row.get('question') or '').strip()
            if not question:
                continue
            normalized_role = self._normalize(str(row.get('role', '')))
            normalized_type = self._normalize(str(row.get('interview_type', '')))

            if self._is_software_only_enabled() and not self._is_software_role(normalized_role):
                continue

            if self._is_software_only_enabled() and normalized_type not in self._allowed_software_types():
                continue

            valid.append({
                'company': self._normalize(str(row.get('company', ''))),
                'role': normalized_role,
                'difficulty': self._normalize(str(row.get('difficulty', ''))),
                'interview_type': normalized_type,
                'question': question,
                'followups': row.get('followups', []) or [],
                'competencies': row.get('competencies', []) or [],
                'tags': [self._normalize(str(t)) for t in (row.get('tags', []) or [])],
            })
        return valid

    def retrieve(
        self,
        *,
        company: str,
        role: str,
        difficulty: str,
        interview_type: str,
        user_transcript: str,
        history: List[Dict[str, str]],
        top_k: int,
    ) -> List[Dict[str, object]]:
        if not self._dataset:
            return []

        candidate_pool = int(getattr(settings, 'INTERVIEW_RAG_CANDIDATE_POOL', 12))
        rerank_enabled = str(getattr(settings, 'INTERVIEW_RAG_ENABLE_RERANK', '1')).lower() in {'1', 'true', 'yes'}
        diversity_lambda = float(getattr(settings, 'INTERVIEW_RAG_DIVERSITY_LAMBDA', 0.2))
        semantic_weight = float(getattr(settings, 'INTERVIEW_RAG_SEMANTIC_WEIGHT', 1.1))
        meta_weight = float(getattr(settings, 'INTERVIEW_RAG_METADATA_WEIGHT', 1.0))

        q_company = self._normalize(company)
        q_role = self._normalize(role)
        q_difficulty = self._normalize(difficulty)
        q_type = self._normalize(interview_type)

        if self._is_software_only_enabled():
            q_role = 'software engineer'
            q_type = self._normalize_software_type(q_type)

        history_text = ' '.join((item.get('user', '') + ' ' + item.get('ai', '')).strip() for item in history[-6:])
        context_tokens = set(self._tokenize(user_transcript) + self._tokenize(history_text))

        scored: List[Dict[str, object]] = []
        for item in self._dataset:
            if self._is_software_only_enabled() and not self._is_software_role(str(item.get('role', ''))):
                continue

            if self._is_software_only_enabled() and q_type and str(item.get('interview_type', '')) != q_type:
                continue

            meta_score = 0.0
            reasons: List[str] = []

            if item['company'] and q_company and item['company'] in q_company:
                meta_score += 4.0
                reasons.append('company match')
                if item['company'] == q_company:
                    meta_score += 2.5
                    reasons.append('company exact')
            if item['role'] and q_role and item['role'] in q_role:
                meta_score += 4.0
                reasons.append('role match')
                if item['role'] == q_role:
                    meta_score += 1.5
                    reasons.append('role exact')
            if item['difficulty'] and q_difficulty and item['difficulty'] == q_difficulty:
                meta_score += 2.0
                reasons.append('difficulty match')
            if item['interview_type'] and q_type and item['interview_type'] == q_type:
                meta_score += 2.0
                reasons.append('type match')

            item_tokens = set(self._tokenize(str(item['question'])))
            for f in item.get('followups', [])[:3]:
                item_tokens.update(self._tokenize(str(f)))
            for t in item.get('tags', []):
                item_tokens.update(self._tokenize(str(t)))

            overlap = len(context_tokens.intersection(item_tokens))
            semantic_score = 0.0
            if overlap:
                for tok in context_tokens.intersection(item_tokens):
                    semantic_score += self._token_idf.get(tok, 1.0)
                semantic_score = min(3.5, semantic_score)
                reasons.append(f'context overlap={overlap}')

            base_score = (meta_weight * meta_score) + (semantic_weight * semantic_score)
            if base_score <= 0:
                continue

            scored.append({
                **item,
                '_meta_score': round(meta_score, 3),
                '_semantic_score': round(semantic_score, 3),
                '_base_score': round(base_score, 3),
                '_tokens': item_tokens,
                'rationale': ', '.join(reasons),
            })

        scored.sort(key=lambda x: float(x.get('_base_score', 0.0)), reverse=True)
        pool = scored[: max(top_k, candidate_pool)]

        if not rerank_enabled:
            result = pool[: max(1, top_k)]
            return [self._finalize_item(item, rank=i + 1, score_key='_base_score') for i, item in enumerate(result)]

        selected: List[Dict[str, object]] = []
        while len(selected) < max(1, top_k) and pool:
            best_idx = -1
            best_mmr = -10**9
            for idx, candidate in enumerate(pool):
                relevance = float(candidate.get('_base_score', 0.0))
                diversity_penalty = 0.0
                if selected:
                    diversity_penalty = max(
                        self._jaccard(candidate.get('_tokens', set()), picked.get('_tokens', set()))
                        for picked in selected
                    )

                mmr_score = ((1.0 - diversity_lambda) * relevance) - (diversity_lambda * diversity_penalty)
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = idx

            if best_idx < 0:
                break

            chosen = pool.pop(best_idx)
            chosen['_mmr_score'] = round(best_mmr, 3)
            selected.append(chosen)

        return [self._finalize_item(item, rank=i + 1, score_key='_mmr_score') for i, item in enumerate(selected)]

    @staticmethod
    def _finalize_item(item: Dict[str, object], rank: int, score_key: str) -> Dict[str, object]:
        score = float(item.get(score_key, item.get('_base_score', 0.0)))
        meta_score = float(item.get('_meta_score', 0.0))
        semantic_score = float(item.get('_semantic_score', 0.0))

        base_rationale = str(item.get('rationale', '')).strip()
        extra = f"meta={meta_score:.2f}, semantic={semantic_score:.2f}, rank={rank}, score={score:.3f}"
        rationale = f"{base_rationale}; {extra}" if base_rationale else extra

        return {
            'company': item.get('company', ''),
            'role': item.get('role', ''),
            'difficulty': item.get('difficulty', ''),
            'interview_type': item.get('interview_type', ''),
            'question': item.get('question', ''),
            'followups': item.get('followups', []) or [],
            'competencies': item.get('competencies', []) or [],
            'tags': item.get('tags', []) or [],
            'score': round(score, 3),
            'rationale': rationale,
        }
