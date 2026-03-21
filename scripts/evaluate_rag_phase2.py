import os
import sys
from pathlib import Path
from typing import Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talvo.settings')

import django  # noqa: E402

django.setup()

from talvo1.rag_retriever import InterviewRAGRetriever  # noqa: E402


def scenario_score(results: List[Dict[str, object]], company: str, role: str, difficulty: str, interview_type: str) -> float:
    if not results:
        return 0.0

    total = 0.0
    top = results[0]

    if company.lower() in str(top.get('company', '')).lower():
        total += 0.35
    if role.lower() in str(top.get('role', '')).lower():
        total += 0.35
    if difficulty.lower() == str(top.get('difficulty', '')).lower():
        total += 0.15
    if interview_type.lower() == str(top.get('interview_type', '')).lower():
        total += 0.15
    return round(total, 3)


def main() -> None:
    retriever = InterviewRAGRetriever()

    scenarios = [
        {
            'name': 'Amazon SDE Technical Medium',
            'company': 'Amazon',
            'role': 'Software Engineer',
            'difficulty': 'Medium',
            'interview_type': 'Technical',
            'transcript': 'I redesigned a service and had to balance p95 latency, retry storms, and database load.',
            'history': [],
        },
        {
            'name': 'Google SDE System Design Hard',
            'company': 'Google',
            'role': 'Software Engineer',
            'difficulty': 'Hard',
            'interview_type': 'System Design',
            'transcript': 'I designed a high-throughput notifications system with multi-region failover and strict SLOs.',
            'history': [],
        },
        {
            'name': 'Microsoft SDE Debugging Hard',
            'company': 'Microsoft',
            'role': 'Software Engineer',
            'difficulty': 'Hard',
            'interview_type': 'Debugging',
            'transcript': 'An intermittent production incident caused elevated error rates and I traced it to connection pool exhaustion.',
            'history': [],
        },
    ]

    print('=== Talvo RAG Phase-2 Evaluation ===')
    print('')

    aggregate = 0.0
    for s in scenarios:
        results = retriever.retrieve(
            company=s['company'],
            role=s['role'],
            difficulty=s['difficulty'],
            interview_type=s['interview_type'],
            user_transcript=s['transcript'],
            history=s['history'],
            top_k=4,
        )
        score = scenario_score(results, s['company'], s['role'], s['difficulty'], s['interview_type'])
        aggregate += score

        print(f"Scenario: {s['name']}")
        print(f"Top-1 alignment score: {score:.3f}")
        if not results:
            print('No retrieval results')
            print('')
            continue

        for idx, item in enumerate(results[:3], start=1):
            print(
                f"  {idx}. [{item.get('company')}/{item.get('role')}/{item.get('difficulty')}/{item.get('interview_type')}] "
                f"score={item.get('score')}"
            )
            print(f"     Q: {item.get('question')}")
            print(f"     Why: {item.get('rationale')}")
        print('')

    avg = aggregate / len(scenarios)
    print(f'Average top-1 alignment score: {avg:.3f}')


if __name__ == '__main__':
    main()
