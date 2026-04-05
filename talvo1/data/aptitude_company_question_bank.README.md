# Company-Wise Aptitude Question Bank

This project now supports loading company-specific aptitude questions from:

- `talvo1/data/aptitude_company_question_bank.json`

## Supported JSON shape

```json
{
  "google": {
    "questions": [
      {
        "id": "gq_1",
        "category": "Quantitative Aptitude",
        "text": "Question text",
        "options": ["A", "B", "C", "D"],
        "answer_index": 2,
        "source_url": "https://example.com/source"
      }
    ]
  },
  "general": {
    "questions": []
  }
}
```

## Rules

- Keys are company names (case-insensitive): `google`, `amazon`, `tcs`, etc.
- `questions` must be a list of valid MCQs.
- Each question requires: `text`, `options` (2+), `answer_index`.
- `id` is optional (auto-generated if omitted).
- `source_url` is optional metadata only.
- If a company has fewer questions, built-in fallback questions are used automatically.

## Important

Only add content you are licensed/allowed to use. If importing from third-party websites, follow their Terms of Use and copyright policy.
