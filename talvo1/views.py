import json
import ast
import csv
import io
import os
import random
import re
import subprocess
import sys
import tempfile
import textwrap
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
import requests

from .forms import RegistrationOnboardingForm
from .interview_pipeline import InterviewPipeline, PipelineUnavailableError
from .models import AptitudeAttempt, InterviewSession, InterviewTurn, UserProfile


_CODING_SESSION_PACKS = {}
_CODING_COMPANY_CACHE = {'names': [], 'loaded': False}
_CODING_FOLLOWUP_STATE = {}
_APTITUDE_EXTERNAL_BANK_CACHE = {'path': '', 'mtime': None, 'data': {}}

_PLACEMENT_COMPANIES = [
	'Google',
	'Microsoft',
	'Amazon',
	'Tech Mahindra',
	'TCS',
	'Infosys',
	'Wipro',
	'Accenture',
	'Cognizant',
	'Capgemini',
	'Deloitte',
	'Flipkart',
	'Zoho',
]

_PLACEMENT_COMPANY_KEYS = [item.lower() for item in _PLACEMENT_COMPANIES]

_PLACEMENT_COMPANY_META = {
	'google': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg',
		'tagline': 'Algorithms, depth, and structured communication',
		'focus': 'Problem solving and scalable thinking',
		'accent': '#0B3D91',
		'accent_secondary': '#1f2f82',
	},
	'microsoft': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg',
		'tagline': 'Practical architecture and implementation clarity',
		'focus': 'System reasoning and execution quality',
		'accent': '#0B3D91',
		'accent_secondary': '#2c5aa0',
	},
	'amazon': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg',
		'tagline': 'Ownership and leadership-principle rigor',
		'focus': 'Behavioral depth with measurable outcomes',
		'accent': '#92400e',
		'accent_secondary': '#b45309',
	},
	'tcs': {
		'logo_static': 'talvo1/images/companies/tcs.svg',
		'tagline': 'Enterprise-grade delivery and reliability',
		'focus': 'Implementation detail and communication clarity',
		'accent': '#0B3D91',
		'accent_secondary': '#1e40af',
	},
	'wipro': {
		'logo_static': 'talvo1/images/companies/wipro.svg',
		'tagline': 'Execution quality in service-led environments',
		'focus': 'Operational ownership and clear delivery',
		'accent': '#0f766e',
		'accent_secondary': '#0d9488',
	},
	'tech mahindra': {
		'logo_static': 'talvo1/images/companies/tech_mahindra.svg',
		'tagline': 'Architecture and operational trade-off thinking',
		'focus': 'Reliability, scale, and solutioning',
		'accent': '#7C4DFF',
		'accent_secondary': '#5b21b6',
	},
	'infosys': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/9/95/Infosys_logo.svg',
		'tagline': 'Digital transformation and enterprise engineering',
		'focus': 'Aptitude speed with delivery-oriented problem solving',
		'accent': '#0B3D91',
		'accent_secondary': '#2563eb',
	},
	'accenture': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/c/cd/Accenture.svg',
		'tagline': 'Consulting-first execution and business impact',
		'focus': 'Structured thinking and communication clarity',
		'accent': '#4c1d95',
		'accent_secondary': '#6d28d9',
	},
	'cognizant': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/4/43/Cognizant_logo_2022.svg',
		'tagline': 'Engineering and service delivery consistency',
		'focus': 'Problem framing with practical implementation',
		'accent': '#0f766e',
		'accent_secondary': '#0891b2',
	},
	'capgemini': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/9/9d/Capgemini_201x_logo.svg',
		'tagline': 'Technology consulting and solution reliability',
		'focus': 'Analytical aptitude and systems mindset',
		'accent': '#2563eb',
		'accent_secondary': '#0ea5e9',
	},
	'deloitte': {
		'logo_url': 'https://cdn.worldvectorlogo.com/logos/deloitte-2.svg',
		'tagline': 'Business insight with technical execution',
		'focus': 'Reasoning strength and case-based communication',
		'accent': '#166534',
		'accent_secondary': '#15803d',
	},
	'flipkart': {
		'logo_url': 'https://cdn.worldvectorlogo.com/logos/flipkart.svg',
		'tagline': 'Scale-ready e-commerce engineering',
		'focus': 'Data-driven decisions and speed under constraints',
		'accent': '#1d4ed8',
		'accent_secondary': '#2563eb',
	},
	'zoho': {
		'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/3/30/ZOHO_logo_2023.svg',
		'tagline': 'Product craftsmanship and practical innovation',
		'focus': 'Fundamental depth with clean implementation',
		'accent': '#b45309',
		'accent_secondary': '#ea580c',
	},
}

_APTITUDE_QUESTIONS_PER_TEST = 10

_APTITUDE_QUESTION_BANK = [
	{
		'id': 'q1',
		'category': 'Quantitative Aptitude',
		'text': 'A number is increased by 20% and then decreased by 20%. What is the net percentage change?',
		'options': ['0%', '4% decrease', '4% increase', '2% decrease'],
		'answer_index': 1,
	},
	{
		'id': 'q2',
		'category': 'Logical Reasoning',
		'text': 'If all coders are problem solvers and some problem solvers are designers, which statement is definitely true?',
		'options': [
			'Some coders are designers',
			'No designers are coders',
			'Some problem solvers may be coders',
			'All designers are coders',
		],
		'answer_index': 2,
	},
	{
		'id': 'q3',
		'category': 'Data Interpretation',
		'text': 'Team A solved 120 questions in 3 hours. Team B solved 150 questions in 5 hours. Which team has a better per-hour rate?',
		'options': ['Team A', 'Team B', 'Both equal', 'Cannot determine'],
		'answer_index': 0,
	},
	{
		'id': 'q4',
		'category': 'Verbal Ability',
		'text': 'Choose the correctly written sentence.',
		'options': [
			'Each of the candidates have submitted their resume.',
			'Each of the candidates has submitted his or her resume.',
			'Each candidate have submitted their resumes.',
			'Each candidate has submitted there resume.',
		],
		'answer_index': 1,
	},
	{
		'id': 'q5',
		'category': 'Quantitative Aptitude',
		'text': 'A train running at 60 km/h crosses a pole in 9 seconds. What is the length of the train?',
		'options': ['120 m', '150 m', '180 m', '200 m'],
		'answer_index': 1,
	},
	{
		'id': 'q6',
		'category': 'Logical Reasoning',
		'text': 'Find the next term: 2, 6, 12, 20, 30, ?',
		'options': ['36', '40', '42', '44'],
		'answer_index': 2,
	},
	{
		'id': 'q7',
		'category': 'Data Interpretation',
		'text': 'A candidate answered 45 out of 60 questions correctly. What is the accuracy percentage?',
		'options': ['70%', '72%', '75%', '80%'],
		'answer_index': 2,
	},
	{
		'id': 'q8',
		'category': 'Verbal Ability',
		'text': 'Pick the best synonym for "meticulous".',
		'options': ['Careless', 'Detailed', 'Rapid', 'Silent'],
		'answer_index': 1,
	},
	{
		'id': 'q9',
		'category': 'Quantitative Aptitude',
		'text': 'What is the simple interest on Rs. 5,000 at 8% per annum for 2 years?',
		'options': ['Rs. 600', 'Rs. 700', 'Rs. 800', 'Rs. 900'],
		'answer_index': 2,
	},
	{
		'id': 'q10',
		'category': 'Logical Reasoning',
		'text': 'If A=1, B=2, C=3, then the code for "CAB" is:',
		'options': ['213', '312', '321', '132'],
		'answer_index': 1,
	},
	{
		'id': 'q11',
		'category': 'Data Interpretation',
		'text': 'Monthly ticket closures are Jan=120, Feb=150, Mar=180, Apr=210. What is the percentage increase from Jan to Apr?',
		'options': ['60%', '70%', '75%', '80%'],
		'answer_index': 2,
	},
	{
		'id': 'q12',
		'category': 'Verbal Ability',
		'text': 'Choose the antonym of "abundant".',
		'options': ['Plentiful', 'Scarce', 'Ample', 'Lavish'],
		'answer_index': 1,
	},
	{
		'id': 'q13',
		'category': 'Quantitative Aptitude',
		'text': 'A mixture has milk and water in the ratio 5:3. If 16 liters are added in total preserving ratio, how much water is added?',
		'options': ['4 liters', '5 liters', '6 liters', '8 liters'],
		'answer_index': 2,
	},
	{
		'id': 'q14',
		'category': 'Logical Reasoning',
		'text': 'In a row of 8 people, Maya is 3rd from left and Riya is 2nd from right. If they swap places, Maya becomes:',
		'options': ['2nd from right', '3rd from right', '4th from right', '5th from left'],
		'answer_index': 0,
	},
	{
		'id': 'q15',
		'category': 'Data Interpretation',
		'text': 'Out of 500 applicants, 340 qualified Round 1. What is the qualification percentage?',
		'options': ['62%', '64%', '66%', '68%'],
		'answer_index': 3,
	},
	{
		'id': 'q16',
		'category': 'Verbal Ability',
		'text': 'Identify the grammatically correct sentence.',
		'options': [
			'Neither of the two candidates were selected.',
			'Neither of the two candidates was selected.',
			'Neither of two candidates have been selected.',
			'Neither candidates was selected.',
		],
		'answer_index': 1,
	},
	{
		'id': 'q17',
		'category': 'Quantitative Aptitude',
		'text': 'A task can be completed by 6 people in 10 days. In how many days can 12 people complete it at the same rate?',
		'options': ['3 days', '4 days', '5 days', '6 days'],
		'answer_index': 2,
	},
	{
		'id': 'q18',
		'category': 'Logical Reasoning',
		'text': 'Find the odd one out.',
		'options': ['Triangle', 'Square', 'Circle', 'Cube'],
		'answer_index': 3,
	},
	{
		'id': 'q19',
		'category': 'Data Interpretation',
		'text': 'A pie chart shows category shares: A=30%, B=25%, C=20%, D=25%. If total is 800, what is count for category C?',
		'options': ['120', '140', '160', '180'],
		'answer_index': 2,
	},
	{
		'id': 'q20',
		'category': 'Verbal Ability',
		'text': 'Fill in the blank: The manager asked the team to submit the report ____ Monday.',
		'options': ['at', 'for', 'by', 'with'],
		'answer_index': 2,
	},
	{
		'id': 'q21',
		'category': 'Quantitative Aptitude',
		'text': 'The average of 18, 22, 26, and x is 24. Find x.',
		'options': ['28', '30', '32', '34'],
		'answer_index': 1,
	},
	{
		'id': 'q22',
		'category': 'Logical Reasoning',
		'text': 'Statements: All testers are analysts. Some analysts are developers. Conclusion: Some testers are developers.',
		'options': ['Definitely true', 'Definitely false', 'Cannot be concluded', 'Both true and false'],
		'answer_index': 2,
	},
	{
		'id': 'q23',
		'category': 'Data Interpretation',
		'text': 'A batch has 240 candidates with ratio of selected to rejected as 3:5. How many were selected?',
		'options': ['75', '80', '90', '95'],
		'answer_index': 2,
	},
	{
		'id': 'q24',
		'category': 'Verbal Ability',
		'text': 'Choose the one-word substitute: "A person who can use both hands equally well".',
		'options': ['Amphibian', 'Ambidextrous', 'Ambiguous', 'Anonymous'],
		'answer_index': 1,
	},
]

_APTITUDE_COMPANY_BANK_PATH = Path(__file__).resolve().parent / 'data' / 'aptitude_company_question_bank.json'

_DEFAULT_COMPANY_RESOURCES = {
	'placement_path': [
		'Round 1: Aptitude and communication screening',
		'Round 2: Technical problem solving with coding basics',
		'Round 3: Hiring manager and HR fit evaluation',
	],
	'aptitude_topics': ['Percentages and ratios', 'Time-speed-distance', 'Logical puzzles', 'Data interpretation sets'],
	'recommended_tracks': [
		'4-week aptitude drill with daily timed sets',
		'Company-specific interview process analysis',
		'Mock interview and final HR answers refinement',
	],
	'resource_links': [
		{'label': 'Aptitude practice set (sample)', 'url': 'https://www.indiabix.com/'},
		{'label': 'DSA quick revision sheet', 'url': 'https://takeuforward.org/interviews/strivers-sde-sheet-top-coding-interview-problems/'},
		{'label': 'Behavioral interview prep', 'url': 'https://www.themuse.com/advice/star-interview-method'},
	],
}

_COMPANY_RESOURCE_OVERRIDES = {
	'google': {
		'placement_path': [
			'Online assessment with problem solving focus',
			'Technical interviews emphasizing data structures and system reasoning',
			'Team fit and leadership conversation',
		],
		'aptitude_topics': ['Quant speed drills', 'Data interpretation', 'Analytical logic', 'Probability basics'],
	},
	'microsoft': {
		'placement_path': [
			'Online coding + aptitude screen',
			'Technical rounds with implementation depth',
			'Behavioral round with collaboration scenarios',
		],
		'aptitude_topics': ['Ratios and averages', 'Reasoning patterns', 'Word problems', 'Case-style logic'],
	},
	'amazon': {
		'placement_path': [
			'Aptitude and coding assessment',
			'Data structures + debugging interview rounds',
			'Leadership principles focused behavioral interview',
		],
		'aptitude_topics': ['Percentages and profit-loss', 'Permutation-combination', 'Logical sequences', 'Interpretive graphs'],
	},
	'tcs': {
		'placement_path': [
			'TCS NQT style aptitude and verbal sections',
			'Basic coding and technical fundamentals interview',
			'HR + communication assessment',
		],
		'aptitude_topics': ['Number systems', 'Time and work', 'Grammar and sentence correction', 'Reasoning grids'],
	},
}


def _normalize_company_name(value: str) -> str:
	text = ' '.join(str(value or '').strip().split())
	if not text:
		return ''
	return text[:140]


def _company_key(company: str) -> str:
	return _normalize_company_name(company).lower()


def _is_combined_company_value(company: str) -> bool:
	text = _normalize_company_name(company).lower()
	if not text:
		return False

	mentions = 0
	for name in _PLACEMENT_COMPANY_KEYS:
		if re.search(rf'\b{re.escape(name)}\b', text):
			mentions += 1

	if mentions >= 2:
		return True

	if 'combined' in text and mentions >= 1:
		return True

	return False


def _placement_company_profile(company: str) -> dict:
	name = _normalize_company_name(company) or 'General'
	key = _company_key(name)
	meta = _PLACEMENT_COMPANY_META.get(key, {})

	logo_url = str(meta.get('logo_url') or '').strip()
	logo_static = str(meta.get('logo_static') or '').strip()
	if not logo_url and logo_static:
		prefix = str(getattr(settings, 'STATIC_URL', '/static/') or '/static/')
		if not prefix.endswith('/'):
			prefix += '/'
		logo_url = f"{prefix}{logo_static.lstrip('/')}"

	return {
		'name': name,
		'key': key,
		'logo_url': logo_url,
		'tagline': str(meta.get('tagline') or 'Placement-focused preparation track'),
		'focus': str(meta.get('focus') or 'Aptitude, resources, and interview readiness'),
		'accent': str(meta.get('accent') or '#0B3D91'),
		'accent_secondary': str(meta.get('accent_secondary') or '#1f2f82'),
	}


def _placement_company_cards(target_company: str = '') -> list:
	cards = []
	for company in _placement_company_options(target_company):
		cards.append(_placement_company_profile(company))
	return cards


def _placement_company_options(target_company: str = '') -> list:
	seen = set()
	ordered = []

	for name in [target_company] + _PLACEMENT_COMPANIES:
		clean = _normalize_company_name(name)
		if not clean:
			continue
		if _is_combined_company_value(clean):
			continue
		key = clean.lower()
		if key in seen:
			continue
		seen.add(key)
		ordered.append(clean)

	return ordered


def _safe_int(value, default=0):
	try:
		return int(value)
	except Exception:
		return default


def _attempt_percentage(score: int, total_questions: int) -> int:
	total = max(1, int(total_questions or 0))
	if int(total_questions or 0) <= 0:
		return 0
	return int(round((int(score or 0) / total) * 100))


def _build_attempt_rows(attempts: list) -> list:
	rows = []
	for attempt in attempts:
		rows.append(
			{
				'id': attempt.id,
				'company': attempt.company,
				'score': attempt.score,
				'total_questions': attempt.total_questions,
				'percentage': _attempt_percentage(attempt.score, attempt.total_questions),
				'duration_seconds': int(attempt.duration_seconds or 0),
				'created_at': attempt.created_at,
			}
		)
	return rows


def _candidate_analysis(company_attempts: list) -> dict:
	if not company_attempts:
		return {
			'readiness_label': 'Not Started',
			'readiness_note': 'Attempt your first aptitude round to unlock personalized analysis.',
			'trend_label': 'No trend yet',
			'trend_note': 'Complete at least two attempts to measure progress.',
			'recommendations': [
				'Attempt one full timed round first.',
				'Review explanations for every incorrect answer.',
				'Use resources section to target weak topics.',
			],
		}

	percentages = [_attempt_percentage(item.score, item.total_questions) for item in company_attempts]
	avg_pct = int(round(sum(percentages) / len(percentages))) if percentages else 0
	best_pct = max(percentages) if percentages else 0
	latest_pct = percentages[0] if percentages else 0
	earliest_pct = percentages[-1] if percentages else 0
	trend_delta = latest_pct - earliest_pct

	if avg_pct >= 80:
		readiness_label = 'High Readiness'
		readiness_note = 'Strong consistency. Focus on speed and test pressure handling.'
	elif avg_pct >= 65:
		readiness_label = 'Medium Readiness'
		readiness_note = 'Good base. Improve accuracy in weak topics and reduce unattempted questions.'
	else:
		readiness_label = 'Building Readiness'
		readiness_note = 'Strengthen fundamentals first, then increase timed practice volume.'

	if trend_delta >= 5:
		trend_label = f'+{trend_delta}% improving trend'
		trend_note = 'Recent performance is moving up. Keep the same revision rhythm.'
	elif trend_delta <= -5:
		trend_label = f'{trend_delta}% declining trend'
		trend_note = 'Recent attempts dropped. Revisit basics and reduce speed errors.'
	else:
		trend_label = 'Stable trend'
		trend_note = 'Performance is stable. Push targeted topic improvement for next jump.'

	recommendations = [
		f'Average score: {avg_pct}% | Best score: {best_pct}%.',
		'Aim for 2 timed attempts per week and track mistake patterns.',
		'Prioritize Data Interpretation and Logical Reasoning when accuracy falls below 70%.',
	]

	return {
		'readiness_label': readiness_label,
		'readiness_note': readiness_note,
		'trend_label': trend_label,
		'trend_note': trend_note,
		'recommendations': recommendations,
	}


def _get_company_resources(company: str) -> dict:
	key = _normalize_company_name(company).lower()
	merged = {
		'placement_path': list(_DEFAULT_COMPANY_RESOURCES['placement_path']),
		'aptitude_topics': list(_DEFAULT_COMPANY_RESOURCES['aptitude_topics']),
		'recommended_tracks': list(_DEFAULT_COMPANY_RESOURCES['recommended_tracks']),
		'resource_links': list(_DEFAULT_COMPANY_RESOURCES['resource_links']),
	}
	override = _COMPANY_RESOURCE_OVERRIDES.get(key, {})
	for item_key, value in override.items():
		merged[item_key] = value
	return merged


def _parse_question_ids(raw_value: str) -> list:
	ids = []
	seen = set()
	for part in str(raw_value or '').split(','):
		qid = part.strip()
		if not qid or qid in seen:
			continue
		seen.add(qid)
		ids.append(qid)
	return ids


def _clean_question_text(value: str, max_len: int = 360) -> str:
	text = ' '.join(str(value or '').strip().split())
	return text[:max_len]


def _sanitize_external_question(raw_question, company_key: str, index: int) -> dict | None:
	if not isinstance(raw_question, dict):
		return None

	text = _clean_question_text(raw_question.get('text'), 360)
	category = _clean_question_text(raw_question.get('category') or 'Aptitude', 80)
	if not text:
		return None

	options_raw = raw_question.get('options')
	if not isinstance(options_raw, list):
		return None

	options = [_clean_question_text(item, 160) for item in options_raw if _clean_question_text(item, 160)]
	if len(options) < 2:
		return None

	answer_index = _safe_int(raw_question.get('answer_index'), -1)
	if answer_index < 0 or answer_index >= len(options):
		return None

	fallback_id = f"ext_{company_key}_{index}"
	qid = _clean_question_text(raw_question.get('id') or fallback_id, 80)
	if not qid:
		qid = fallback_id

	question = {
		'id': qid,
		'category': category,
		'text': text,
		'options': options,
		'answer_index': answer_index,
	}

	source_url = _clean_question_text(raw_question.get('source_url') or '', 300)
	if source_url:
		question['source_url'] = source_url

	return question


def _load_external_company_questions() -> dict:
	configured_path = str(getattr(settings, 'APTITUDE_COMPANY_QUESTION_BANK_PATH', '') or '').strip()
	bank_path = Path(configured_path) if configured_path else _APTITUDE_COMPANY_BANK_PATH
	cache_key = str(bank_path)

	if not bank_path.exists() or not bank_path.is_file():
		_APTITUDE_EXTERNAL_BANK_CACHE.update({'path': cache_key, 'mtime': None, 'data': {}})
		return {}

	try:
		mtime = bank_path.stat().st_mtime
	except OSError:
		return {}

	if (
		_APTITUDE_EXTERNAL_BANK_CACHE.get('path') == cache_key
		and _APTITUDE_EXTERNAL_BANK_CACHE.get('mtime') == mtime
	):
		return dict(_APTITUDE_EXTERNAL_BANK_CACHE.get('data') or {})

	try:
		with bank_path.open('r', encoding='utf-8') as handle:
			payload = json.load(handle)
	except (OSError, json.JSONDecodeError):
		_APTITUDE_EXTERNAL_BANK_CACHE.update({'path': cache_key, 'mtime': mtime, 'data': {}})
		return {}

	if not isinstance(payload, dict):
		_APTITUDE_EXTERNAL_BANK_CACHE.update({'path': cache_key, 'mtime': mtime, 'data': {}})
		return {}

	parsed = {}
	for company_name, raw_section in payload.items():
		company_key = _company_key(company_name)
		if not company_key:
			continue

		raw_questions = []
		if isinstance(raw_section, list):
			raw_questions = raw_section
		elif isinstance(raw_section, dict):
			raw_questions = raw_section.get('questions') if isinstance(raw_section.get('questions'), list) else []

		questions = []
		seen_ids = set()
		for idx, raw_question in enumerate(raw_questions, start=1):
			sanitized = _sanitize_external_question(raw_question, company_key, idx)
			if not sanitized:
				continue
			qid = sanitized['id']
			if qid in seen_ids:
				continue
			seen_ids.add(qid)
			questions.append(sanitized)

		if questions:
			parsed[company_key] = questions

	_APTITUDE_EXTERNAL_BANK_CACHE.update({'path': cache_key, 'mtime': mtime, 'data': parsed})
	return dict(parsed)


def _company_aptitude_question_bank(company: str) -> list:
	key = _company_key(company)
	external_map = _load_external_company_questions()
	external_questions = list(external_map.get(key) or external_map.get('general') or [])

	if not external_questions:
		return list(_APTITUDE_QUESTION_BANK)

	merged = []
	seen_ids = set()
	for question in external_questions + list(_APTITUDE_QUESTION_BANK):
		qid = str(question.get('id') or '').strip()
		if not qid or qid in seen_ids:
			continue
		seen_ids.add(qid)
		merged.append(question)

	return merged


def _pick_random_question_ids(question_bank: list) -> list:
	category_map = {}
	for question in question_bank:
		category_map.setdefault(question['category'], []).append(question['id'])

	rng = random.SystemRandom()
	selected = []
	for ids in category_map.values():
		pick_count = min(2, len(ids))
		selected.extend(rng.sample(ids, pick_count))

	remaining = [q['id'] for q in question_bank if q['id'] not in selected]
	needed = max(0, _APTITUDE_QUESTIONS_PER_TEST - len(selected))
	if needed and remaining:
		selected.extend(rng.sample(remaining, min(needed, len(remaining))))

	rng.shuffle(selected)
	return selected[:_APTITUDE_QUESTIONS_PER_TEST]


def _get_aptitude_questions(company: str, question_ids: list = None) -> tuple[list, list]:
	company_name = _normalize_company_name(company) or 'your target company'
	company_bank = _company_aptitude_question_bank(company_name)
	bank_by_id = {item['id']: item for item in company_bank}

	resolved_ids = []
	for qid in list(question_ids or []):
		if qid in bank_by_id and qid not in resolved_ids:
			resolved_ids.append(qid)

	if not resolved_ids:
		resolved_ids = _pick_random_question_ids(company_bank)

	questions = []
	for qid in resolved_ids:
		if qid not in bank_by_id:
			continue
		raw = dict(bank_by_id[qid])
		raw['text'] = str(raw.get('text', '')).replace('{company}', company_name)
		questions.append(raw)

	if not questions:
		fallback_bank_by_id = {item['id']: item for item in _APTITUDE_QUESTION_BANK}
		fallback_ids = _pick_random_question_ids(list(_APTITUDE_QUESTION_BANK))
		resolved_ids = fallback_ids
		for qid in fallback_ids:
			raw = dict(fallback_bank_by_id[qid])
			raw['text'] = str(raw.get('text', '')).replace('{company}', company_name)
			questions.append(raw)

	return questions, resolved_ids


def _aptitude_coach_fallback(question_payload: dict, user_prompt: str) -> str:
	question_text = str(question_payload.get('question') or '').strip()
	selected_option = str(question_payload.get('selected_option') or '').strip()
	answer_option = str(question_payload.get('answer_option') or '').strip()
	category = str(question_payload.get('category') or 'Aptitude').strip()
	is_correct = bool(question_payload.get('is_correct'))
	user_prompt = str(user_prompt or '').strip()

	if is_correct:
		return (
			"You got this one correct. To make it interview-ready, explain your approach in 2-3 steps: "
			"1) identify the concept, 2) apply the formula or elimination logic, 3) verify quickly with a sanity check. "
			f"If needed, I can give a faster method for this {category.lower()} question."
		)

	parts = [
		f"Let's break this down for {category}.",
	]
	if selected_option:
		parts.append(f"You selected: {selected_option}.")
	if answer_option:
		parts.append(f"Correct answer: {answer_option}.")

	parts.append(
		"What likely went wrong: either a calculation slip, missing key condition, or rushing option elimination. "
		"Try this method next time: read the exact ask, estimate rough range first, then compute only once."
	)

	if user_prompt:
		parts.append(
			f"Your question was: '{user_prompt}'. Based on that, focus on the exact step where your approach diverged from the condition in the question."
		)

	if question_text:
		parts.append("If you want, ask me 'solve this step by step' and I will walk through this exact question.")

	return ' '.join(parts)


def _aptitude_coach_answer(selected_company: str, question_payload: dict, user_prompt: str, chat_history: list | None = None) -> str:
	question_text = str(question_payload.get('question') or '').strip()
	selected_option = str(question_payload.get('selected_option') or '').strip()
	answer_option = str(question_payload.get('answer_option') or '').strip()
	category = str(question_payload.get('category') or 'Aptitude').strip()
	is_correct = bool(question_payload.get('is_correct'))
	user_prompt = str(user_prompt or '').strip()[:600]

	if not question_text:
		return 'Please select a question first so I can explain what went wrong and how to improve.'

	try:
		pipeline = InterviewPipeline.instance()
		pipeline._ensure_models()
		model_name = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant')

		history_lines = []
		for turn in list(chat_history or [])[-6:]:
			role = str(turn.get('role') or '').strip().lower()
			content = str(turn.get('content') or '').strip()
			if role not in {'user', 'assistant'} or not content:
				continue
			history_lines.append(f"{role}: {content}")

		prompt = (
			"You are Talvo Aptitude AI Coach. Be concise, practical, and beginner-friendly. "
			"For wrong answers: explain where mistake usually happens, then give a corrected approach and one quick tip. "
			"Do not invent facts outside the question details.\n\n"
			f"Company context: {selected_company}\n"
			f"Category: {category}\n"
			f"Question: {question_text}\n"
			f"User selected option: {selected_option or 'Not attempted'}\n"
			f"Correct option: {answer_option or 'Unavailable'}\n"
			f"Is user correct: {is_correct}\n"
			f"Prior chat (optional): {' | '.join(history_lines) if history_lines else 'None'}\n"
			f"User asks: {user_prompt or 'What went wrong in this question?'}\n\n"
			"Return plain text in under 180 words."
		)

		resp = pipeline._groq.chat.completions.create(
			model=model_name,
			temperature=0.2,
			max_tokens=260,
			messages=[
				{'role': 'system', 'content': 'You are an aptitude correction coach.'},
				{'role': 'user', 'content': prompt},
			],
		)
		content = str(resp.choices[0].message.content or '').strip()
		if content:
			return content
	except Exception:
		pass

	return _aptitude_coach_fallback(question_payload, user_prompt)


def landing(request):
	return render(request, 'Landing-Page-00f62077fa864a1cace2f0ef0ea59f18.html')


def auth_login(request):
	if request.user.is_authenticated:
		return redirect('post_login_redirect')
	return render(request, 'auth/login.html')


@login_required
def post_login_redirect(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	if not profile.profile_completed:
		return redirect('registration_onboarding')
	return redirect('dashboard')


@login_required
def registration_onboarding(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	if profile.profile_completed:
		return redirect('dashboard')

	if request.method == 'POST':
		form = RegistrationOnboardingForm(request.POST, instance=profile)
		if form.is_valid():
			onboarding = form.save(commit=False)
			onboarding.profile_completed = True
			onboarding.save()
			return redirect('dashboard')
	else:
		form = RegistrationOnboardingForm(instance=profile)

	return render(request, 'auth/registration_onboarding.html', {'form': form})


@login_required
def logout_user(request):
	if request.method == 'POST':
		logout(request)
	return redirect('landing')


@login_required
def talvo_ai_interview_prep(request):
	return render(request, 'Talvo-AI-Interview-Prep-1ef0427fbbae4f41bdb3c4e538160e37.html')


@login_required
def dashboard(request):
	return render(request, 'Dashboard-5405ed6ef83247c3bd20866b24684c91.html')


@login_required
def placement_hub(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	profile_company = _normalize_company_name(profile.target_company or '')
	if _is_combined_company_value(profile_company):
		profile_company = ''

	company_options = _placement_company_options(profile_company)
	company_cards = _placement_company_cards(profile_company)
	selected_company = _normalize_company_name(request.GET.get('company') or profile_company or '')
	if _is_combined_company_value(selected_company):
		selected_company = ''

	if request.method == 'POST':
		selected_company = _normalize_company_name(request.POST.get('selected_company') or request.POST.get('target_company') or profile_company or '')
		if _is_combined_company_value(selected_company):
			selected_company = ''

		if not selected_company:
			selected_company = profile_company or 'General'

		return redirect(f"{reverse('placement_company')}?company={quote(selected_company)}")

	attempts_qs = AptitudeAttempt.objects.filter(user=request.user)
	latest_attempt = attempts_qs.order_by('-created_at').first()
	best_attempt = attempts_qs.order_by('-score', '-created_at').first()
	overall_avg = attempts_qs.aggregate(avg_score=Avg('score')).get('avg_score')

	context = {
		'company_options': company_options,
		'company_cards': company_cards,
		'selected_company': selected_company,
		'total_aptitude_attempts': attempts_qs.count(),
		'latest_attempt': latest_attempt,
		'best_attempt': best_attempt,
		'overall_avg_score': int(round(overall_avg or 0)),
	}
	return render(request, 'Placement-Hub.html', context)


@login_required
def placement_company(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	profile_company = _normalize_company_name(profile.target_company or '')
	if _is_combined_company_value(profile_company):
		profile_company = ''

	selected_company = _normalize_company_name(request.GET.get('company') or profile_company or '')
	if _is_combined_company_value(selected_company):
		selected_company = ''
	if not selected_company:
		selected_company = 'General'

	company_profile = _placement_company_profile(selected_company)
	company_attempts_qs = AptitudeAttempt.objects.filter(user=request.user, company__iexact=selected_company).order_by('-created_at')
	company_attempts = list(company_attempts_qs[:10])
	company_rows = _build_attempt_rows(company_attempts)

	overall_attempts = list(AptitudeAttempt.objects.filter(user=request.user).order_by('-created_at')[:8])
	overall_rows = _build_attempt_rows(overall_attempts)

	latest_company = company_attempts[0] if company_attempts else None
	best_company = company_attempts_qs.order_by('-score', '-created_at').first()
	company_avg = company_attempts_qs.aggregate(avg_score=Avg('score')).get('avg_score')

	resources = _get_company_resources(selected_company)
	analysis = _candidate_analysis(company_attempts)

	context = {
		'selected_company': selected_company,
		'company_profile': company_profile,
		'company_attempt_rows': company_rows,
		'overall_attempt_rows': overall_rows,
		'company_attempt_count': company_attempts_qs.count(),
		'latest_company_attempt': latest_company,
		'latest_company_percentage': _attempt_percentage(latest_company.score, latest_company.total_questions) if latest_company else 0,
		'best_company_attempt': best_company,
		'best_company_percentage': _attempt_percentage(best_company.score, best_company.total_questions) if best_company else 0,
		'company_avg_score': int(round(company_avg or 0)),
		'analysis': analysis,
		'resource_preview': resources,
	}
	return render(request, 'Placement-Company.html', context)


@login_required
def aptitude_round(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	selected_company = _normalize_company_name(
		request.GET.get('company') if request.method != 'POST' else request.POST.get('company')
	)
	if not selected_company:
		selected_company = _normalize_company_name(profile.target_company) or 'General'
	company_profile = _placement_company_profile(selected_company)

	posted_question_ids = _parse_question_ids(request.POST.get('question_ids')) if request.method == 'POST' else []
	questions, question_ids = _get_aptitude_questions(
		selected_company,
		posted_question_ids if request.method == 'POST' else None,
	)
	result = None
	aptitude_results_payload = None
	selected_answers = {}

	if request.method == 'POST':
		duration_seconds = max(0, _safe_int(request.POST.get('duration_seconds'), 0))
		review = []
		score = 0

		for question in questions:
			field_name = f"q_{question['id']}"
			selected_index = _safe_int(request.POST.get(field_name), -1)
			selected_answers[question['id']] = selected_index
			is_correct = selected_index == int(question['answer_index'])
			if is_correct:
				score += 1
			answer_index = int(question['answer_index'])
			options = list(question['options'])
			selected_option = options[selected_index] if 0 <= selected_index < len(options) else ''
			answer_option = options[answer_index] if 0 <= answer_index < len(options) else ''
			review.append(
				{
					'id': question['id'],
					'question': question['text'],
					'category': question['category'],
					'options': options,
					'selected_index': selected_index,
					'answer_index': answer_index,
					'selected_option': selected_option,
					'answer_option': answer_option,
					'is_correct': is_correct,
				}
			)

		total_questions = len(questions)
		attempt = AptitudeAttempt.objects.create(
			user=request.user,
			company=selected_company,
			score=score,
			total_questions=total_questions,
			duration_seconds=duration_seconds,
			responses=selected_answers,
		)
		percentage = int(round((score / total_questions) * 100)) if total_questions else 0
		result = {
			'attempt_id': attempt.id,
			'score': score,
			'total_questions': total_questions,
			'percentage': percentage,
			'duration_seconds': duration_seconds,
			'review': review,
		}

	if result:
		aptitude_results_payload = {
			'company_name': selected_company,
			'company_logo_url': company_profile.get('logo_url') or '',
			'summary': {
				'score': int(result.get('score') or 0),
				'total_questions': int(result.get('total_questions') or 0),
				'percentage': int(result.get('percentage') or 0),
				'duration_seconds': int(result.get('duration_seconds') or 0),
			},
			'review': list(result.get('review') or []),
			'urls': {
				'retake': f"{reverse('aptitude_round')}?company={quote(selected_company)}",
				'resources': f"{reverse('company_resources')}?company={quote(selected_company)}",
				'workspace': f"{reverse('placement_company')}?company={quote(selected_company)}",
				'coach_api': reverse('aptitude_coach_api'),
			},
		}

	context = {
		'selected_company': selected_company,
		'company_profile': company_profile,
		'questions': questions,
		'question_ids_csv': ','.join(question_ids),
		'question_count': len(questions),
		'result': result,
		'aptitude_results_payload': aptitude_results_payload,
		'selected_answers': selected_answers,
	}
	return render(request, 'Aptitude-Round.html', context)


@login_required
@require_POST
def aptitude_coach_api(request):
	try:
		payload = json.loads(request.body.decode('utf-8') or '{}')
	except json.JSONDecodeError:
		return JsonResponse({'ok': False, 'error': 'Invalid JSON payload'}, status=400)

	selected_company = _normalize_company_name(payload.get('company') or '') or 'General'
	question_payload = payload.get('question') if isinstance(payload.get('question'), dict) else {}
	user_prompt = str(payload.get('prompt') or '').strip()
	chat_history = payload.get('history') if isinstance(payload.get('history'), list) else []

	if not isinstance(question_payload, dict) or not str(question_payload.get('question') or '').strip():
		return JsonResponse({'ok': False, 'error': 'Question context is required'}, status=400)

	answer = _aptitude_coach_answer(selected_company, question_payload, user_prompt, chat_history)
	return JsonResponse({'ok': True, 'answer': answer})


@login_required
def company_resources(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	selected_company = _normalize_company_name(request.GET.get('company') or profile.target_company or '')
	if not selected_company:
		selected_company = 'General'

	context = {
		'selected_company': selected_company,
		'company_profile': _placement_company_profile(selected_company),
		'company_resources': _get_company_resources(selected_company),
	}
	return render(request, 'Company-Resources.html', context)


@login_required
def history_page(request):
	context = _build_results_context(request.user)
	return render(request, 'History-Page-a3d819cc716944daa8cb80c50d943ada.html', context)


@login_required
def interview_setup(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	has_resume = bool((profile.resume_text or '').strip())
	return render(
		request,
		'Interview-Setup-82549d84a8874a5d8a6eac01c3e830e0.html',
		{'has_resume': has_resume},
	)


@login_required
def live_interview(request):
	prefill_role, prefill_type = _enforce_software_focus(
		request.GET.get('role', ''),
		request.GET.get('type', ''),
	)
	prefill_round = (request.GET.get('round', '') or '').strip().lower()
	if prefill_round not in {'technical', 'final'}:
		prefill_round = 'final' if 'final' in prefill_type.lower() else 'technical'
	context = {
		'prefill_role': prefill_role,
		'prefill_company': request.GET.get('company', ''),
		'prefill_difficulty': request.GET.get('difficulty', 'Medium'),
		'prefill_type': prefill_type,
		'prefill_round': prefill_round,
		'prefill_mode': request.GET.get('mode', 'avatar'),
		'prefill_include_resume': _as_bool(request.GET.get('include_resume', '0')),
	}
	return render(request, 'Live-Interview-36d6010513664b89ae2c813c331e830e.html', context)


def _session_history(session: InterviewSession):
	history = []
	for turn in session.turns.all().order_by('turn_index'):
		history.append({'user': turn.user_transcript, 'ai': turn.ai_response})
	return history


def _build_audio_paths(session: InterviewSession, turn_index: int):
	base_rel = f"interviews/session_{session.id}"
	user_rel = f"{base_rel}/user_turn_{turn_index}.webm"
	ai_rel = f"{base_rel}/ai_turn_{turn_index}.wav"
	return user_rel, ai_rel


def _build_media_url(request, rel_path: str):
	clean = rel_path.replace('\\', '/')
	base = settings.MEDIA_URL
	if not base.endswith('/'):
		base += '/'
	return request.build_absolute_uri(f"{base}{clean}")


def _as_bool(value) -> bool:
	if isinstance(value, bool):
		return value
	text = str(value or '').strip().lower()
	return text in {'1', 'true', 'yes', 'on'}


def _decode_pdf_literal_string(raw: str) -> str:
	if not raw:
		return ''
	# Handle common PDF string escapes used in tagged/accessible PDFs.
	text = raw.replace(r'\(', '(').replace(r'\)', ')').replace(r'\\', '\\')
	text = re.sub(r'\\([0-7]{1,3})', lambda m: chr(int(m.group(1), 8)), text)
	return text


def _extract_structured_pdf_text(raw_bytes: bytes, max_chars: int) -> str:
	if not raw_bytes:
		return ''

	decoded = raw_bytes.decode('latin-1', errors='ignore')
	chunks = []

	# Tagged PDFs often store semantic text in /E (...) or /E <...> nodes.
	for match in re.finditer(r'/E\s*\((.*?)\)', decoded, flags=re.DOTALL):
		literal = _decode_pdf_literal_string(match.group(1)).strip()
		if literal:
			chunks.append(literal)

	for match in re.finditer(r'/E\s*<([0-9A-Fa-f]+)>', decoded):
		hex_data = match.group(1)
		if len(hex_data) % 2:
			continue
		try:
			blob = bytes.fromhex(hex_data)
		except Exception:
			continue
		for codec in ('utf-16-be', 'utf-8', 'latin-1'):
			try:
				literal = blob.decode(codec, errors='ignore').strip()
			except Exception:
				literal = ''
			if literal:
				chunks.append(literal)
				break

	if not chunks:
		return ''

	seen = set()
	ordered = []
	for item in chunks:
		item = item.replace('\x00', ' ').strip()
		if not item:
			continue
		key = item.lower()
		if key in seen:
			continue
		seen.add(key)
		ordered.append(item)

	return '\n'.join(ordered).strip()[:max_chars]


def _normalize_extracted_text(text: str, max_chars: int) -> str:
	if not text:
		return ''
	clean = str(text).replace('\x00', ' ').replace('\ufeff', ' ')
	clean = re.sub(r'[\u200b-\u200f\u2060]', '', clean)
	clean = clean.replace('\r\n', '\n').replace('\r', '\n')
	clean = re.sub(r'[ \t\f\v]+', ' ', clean)
	clean = re.sub(r'\n{3,}', '\n\n', clean)
	return clean.strip()[:max_chars]


def _text_quality_score(text: str) -> int:
	if not text:
		return 0
	normalized = str(text)
	alnum_count = sum(1 for ch in normalized if ch.isalnum())
	word_count = len(re.findall(r'[A-Za-z0-9][A-Za-z0-9+#./-]*', normalized))
	line_count = len([ln for ln in normalized.splitlines() if ln.strip()])
	# Prioritize candidates with actual words, not sparse glyph output.
	return (alnum_count * 3) + (word_count * 10) + (line_count * 4)


def _pick_best_text(candidates, max_chars: int) -> str:
	best_text = ''
	best_score = 0
	for raw in candidates:
		candidate = _normalize_extracted_text(raw, max_chars)
		score = _text_quality_score(candidate)
		if score > best_score:
			best_score = score
			best_text = candidate
	return best_text


def _extract_resume_text(upload) -> str:
	if not upload:
		return ''

	name = str(getattr(upload, 'name', '') or '')
	ext = os.path.splitext(name)[1].lower()
	max_chars = 20000

	if ext in {'.txt', '.md', '.rst'}:
		raw = upload.read()
		if isinstance(raw, bytes):
			text = raw.decode('utf-8', errors='ignore')
		else:
			text = str(raw)
		upload.seek(0)
		return _normalize_extracted_text(text, max_chars)

	if ext == '.pdf':
		try:
			raw = upload.read()
			upload.seek(0)
			if not isinstance(raw, bytes):
				raw = bytes(raw or b'')
			candidates = []

			# 1) pdfplumber: strong on many resume templates.
			try:
				import pdfplumber
				chunks = []
				with pdfplumber.open(io.BytesIO(raw)) as pdf:
					for page in pdf.pages:
						page_text = (page.extract_text() or '').strip()
						if page_text:
							chunks.append(page_text)
						layout_text = (page.extract_text(layout=True) or '').strip()
						if layout_text and layout_text != page_text:
							chunks.append(layout_text)
				if chunks:
					candidates.append('\n'.join(chunks))
			except Exception:
				pass

			# 2) pypdf: fallback for documents where pdfplumber under-extracts.
			try:
				from pypdf import PdfReader
				reader = PdfReader(io.BytesIO(raw))
				chunks = []
				for page in reader.pages:
					page_text = ''
					try:
						page_text = (page.extract_text() or '').strip()
					except Exception:
						page_text = ''
					if not page_text:
						try:
							page_text = (page.extract_text(extraction_mode='layout') or '').strip()
						except Exception:
							page_text = ''
					if page_text:
						chunks.append(page_text)
				if chunks:
					candidates.append('\n'.join(chunks))
			except Exception:
				pass

			# 3) PyMuPDF: catches PDFs where pypdf/pdfplumber miss text ordering.
			try:
				import fitz  # PyMuPDF
				doc = fitz.open(stream=raw, filetype='pdf')
				chunks = []
				for page in doc:
					text_page = (page.get_text('text') or '').strip()
					if text_page:
						chunks.append(text_page)
					block_text = (page.get_text('blocks') or [])
					if block_text:
						block_lines = []
						for block in block_text:
							if isinstance(block, (list, tuple)) and len(block) >= 5:
								val = str(block[4] or '').strip()
								if val:
									block_lines.append(val)
						if block_lines:
							chunks.append('\n'.join(block_lines))
				doc.close()
				if chunks:
					candidates.append('\n'.join(chunks))
			except Exception:
				pass

			# 4) Low-level tagged PDF fallback.
			structured = _extract_structured_pdf_text(raw, max_chars)
			if structured:
				candidates.append(structured)

			text = _pick_best_text(candidates, max_chars)
			upload.seek(0)
			return text
		except Exception:
			upload.seek(0)
			return ''

	if ext == '.docx':
		try:
			from docx import Document
			doc = Document(upload)
			lines = [p.text.strip() for p in doc.paragraphs if (p.text or '').strip()]
			upload.seek(0)
			return _normalize_extracted_text('\n'.join(lines), max_chars)
		except Exception:
			upload.seek(0)
			return ''

	try:
		raw = upload.read()
		if isinstance(raw, bytes):
			text = raw.decode('utf-8', errors='ignore')
		else:
			text = str(raw)
		upload.seek(0)
		return _normalize_extracted_text(text, max_chars)
	except Exception:
		try:
			upload.seek(0)
		except Exception:
			pass
		return ''


def _extract_resume_signals(resume_text: str) -> dict:
	text = str(resume_text or '').strip()
	if not text:
		return {'skills': [], 'projects': [], 'highlights': []}

	lower = text.lower()
	known_skills = [
		'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust',
		'django', 'flask', 'fastapi', 'react', 'node', 'spring',
		'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
		'sql', 'postgresql', 'mysql', 'mongodb', 'redis',
		'git', 'linux', 'ci/cd', 'machine learning', 'deep learning', 'nlp',
	]

	found_skills = []
	for skill in known_skills:
		if skill in lower:
			found_skills.append(skill)

	lines = [ln.strip(' \t-•*') for ln in text.splitlines() if ln.strip()]
	project_lines = []
	highlights = []

	project_zone = False
	for line in lines:
		l = line.lower()
		if any(tag in l for tag in ['project', 'projects', 'work experience', 'experience']):
			project_zone = True
			continue
		if project_zone and any(tag in l for tag in ['education', 'certification', 'skills', 'achievements']):
			project_zone = False
		if project_zone and len(project_lines) < 8:
			project_lines.append(line)
		if any(tok in l for tok in ['built', 'developed', 'designed', 'implemented', 'improved', 'optimized', 'reduced', 'increased']) and len(highlights) < 8:
			highlights.append(line)

	return {
		'skills': found_skills[:20],
		'projects': project_lines[:8],
		'highlights': highlights[:8],
	}


def _build_resume_context_blob(resume_text: str) -> str:
	signals = _extract_resume_signals(resume_text)
	short_text = str(resume_text or '').strip()
	if len(short_text) > 2600:
		short_text = short_text[:2600] + '...'

	skills = ', '.join(signals.get('skills', [])[:15]) or 'Not clearly extracted'
	projects = signals.get('projects', []) or ['Not clearly extracted']
	highlights = signals.get('highlights', []) or ['Not clearly extracted']

	project_block = '\n'.join(f'- {p}' for p in projects[:6])
	highlight_block = '\n'.join(f'- {h}' for h in highlights[:6])

	return (
		'Resume analysis summary:\n'
		f'Skills inferred: {skills}\n'
		f'Projects inferred:\n{project_block}\n'
		f'Experience highlights:\n{highlight_block}\n\n'
		'Resume text excerpt:\n'
		f'{short_text}'
	)


def _extract_candidate_name_from_resume_text(resume_text: str) -> str:
	text = str(resume_text or '').strip()
	if not text:
		return ''

	lines = [ln.strip(' \t-•*') for ln in text.splitlines() if ln.strip()]
	if not lines:
		return ''

	for line in lines[:20]:
		match = re.match(r'^(?:name|candidate|full\s*name)\s*[:\-]\s*(.+)$', line, flags=re.IGNORECASE)
		if not match:
			continue
		value = ' '.join(match.group(1).strip().split())
		if re.match(r'^[A-Za-z][A-Za-z\'\-\.]+(?:\s+[A-Za-z][A-Za-z\'\-\.]*){0,3}$', value):
			return value[:80]

	for line in lines[:6]:
		candidate = ' '.join(line.split())
		if len(candidate) < 2 or len(candidate) > 80:
			continue
		if '@' in candidate or any(ch.isdigit() for ch in candidate):
			continue
		if re.search(r'\b(resume|curriculum vitae|cv|phone|email|linkedin|github|address|experience|education|skills)\b', candidate, flags=re.IGNORECASE):
			continue
		if re.match(r'^[A-Za-z][A-Za-z\'\-\.]+(?:\s+[A-Za-z][A-Za-z\'\-\.]*){0,3}$', candidate):
			return candidate[:80]

	return ''


def _resolve_candidate_name(*, user, include_resume: bool, resume_text: str) -> str:
	if include_resume:
		name_from_resume = _extract_candidate_name_from_resume_text(resume_text)
		if name_from_resume:
			return name_from_resume

	first = str(getattr(user, 'first_name', '') or '').strip()
	last = str(getattr(user, 'last_name', '') or '').strip()
	full = ' '.join(part for part in [first, last] if part).strip()
	if full:
		return full[:80]

	username = str(getattr(user, 'username', '') or '').strip()
	if username:
		return username[:80]

	email = str(getattr(user, 'email', '') or '').strip()
	if email and '@' in email:
		return email.split('@', 1)[0][:80]

	return ''


def _refresh_resume_text_from_saved_file(profile: UserProfile) -> str:
	if (profile.resume_text or '').strip():
		return profile.resume_text.strip()

	if not profile.resume_file:
		return ''

	try:
		profile.resume_file.open('rb')
		text = _extract_resume_text(profile.resume_file)
	finally:
		try:
			profile.resume_file.close()
		except Exception:
			pass

	if text.strip():
		profile.resume_text = text
		profile.save(update_fields=['resume_text', 'updated_at'])
	return text.strip()


def _enforce_software_focus(role: str, interview_type: str):
	enabled = str(getattr(settings, 'INTERVIEW_SOFTWARE_ONLY', '1')).strip().lower() in {'1', 'true', 'yes', 'on'}
	if not enabled:
		return (role or '').strip() or 'Software Engineer', (interview_type or '').strip() or 'Technical'

	requested_raw = (interview_type or '').strip()
	requested = requested_raw.lower()
	if requested in {'final round', 'final'}:
		return 'Software Engineer', 'Final Round'
	if requested in {'technical coding', 'technical round'}:
		return 'Software Engineer', 'Technical Coding'

	allowed_raw = str(getattr(settings, 'INTERVIEW_SOFTWARE_ALLOWED_TYPES', 'technical,coding,system design,debugging,behavioral'))
	allowed = [x.strip().lower() for x in allowed_raw.split(',') if x.strip()]
	pretty = {
		'technical': 'Technical',
		'coding': 'Coding',
		'system design': 'System Design',
		'debugging': 'Debugging',
		'behavioral': 'Behavioral',
	}

	chosen = 'technical'
	if requested in allowed:
		chosen = requested
	else:
		for value in allowed:
			if requested and (requested in value or value in requested):
				chosen = value
				break

	return 'Software Engineer', pretty.get(chosen, 'Technical')


def _build_user_metrics_context(user):
	profile, _ = UserProfile.objects.get_or_create(user=user)
	sessions = InterviewSession.objects.filter(user=user)
	turns = InterviewTurn.objects.filter(session__user=user)

	total_sessions = sessions.count()
	completed_sessions = sessions.filter(status=InterviewSession.STATUS_COMPLETED).count()
	aborted_sessions = sessions.filter(status=InterviewSession.STATUS_ABORTED).count()
	active_sessions = sessions.filter(status=InterviewSession.STATUS_ACTIVE).count()
	avg_processing_ms = int(turns.aggregate(avg=Avg('processing_ms')).get('avg') or 0)

	profile_fields = [
		bool((profile.target_role or '').strip()),
		bool((profile.experience_level or '').strip()),
		bool((profile.target_company or '').strip()),
		bool((profile.interview_focus or '').strip()),
		profile.confidence_level is not None,
	]
	profile_completion = int((sum(1 for value in profile_fields if value) / len(profile_fields)) * 100)

	today = timezone.now().date()
	weekly_labels = []
	weekly_session_counts = []
	for days_ago in range(6, -1, -1):
		day = today - timedelta(days=days_ago)
		weekly_labels.append(day.strftime('%a'))
		weekly_session_counts.append(sessions.filter(started_at__date=day).count())

	top_companies = list(
		sessions.values('target_company')
		.annotate(total=Count('id'))
		.order_by('-total', 'target_company')[:4]
	)

	recent_sessions = sessions.order_by('-started_at')[:5]

	return {
		'profile': profile,
		'total_sessions': total_sessions,
		'completed_sessions': completed_sessions,
		'aborted_sessions': aborted_sessions,
		'active_sessions': active_sessions,
		'avg_processing_ms': avg_processing_ms,
		'profile_completion': profile_completion,
		'weekly_labels': weekly_labels,
		'weekly_session_counts': weekly_session_counts,
		'top_companies': top_companies,
		'recent_sessions': recent_sessions,
	}


def _clamp_score(value: int) -> int:
	if value < 0:
		return 0
	if value > 100:
		return 100
	return value


def _session_review_text(score: int, turn_count: int) -> str:
	if turn_count <= 1:
		return 'Early session signal only. Complete a few more turns for stable feedback trends.'
	if score >= 85:
		return 'Strong interview performance with good depth and consistency. Continue sharpening concise tradeoff explanations.'
	if score >= 72:
		return 'Solid baseline performance. Improve precision in examples and add clearer metrics when describing decisions.'
	if score >= 60:
		return 'Developing performance. Focus on structured answers and concrete failure-mode reasoning.'
	return 'Needs improvement. Practice fundamentals, communicate assumptions explicitly, and answer with clearer step-by-step logic.'


def _build_results_context(user):
	sessions = InterviewSession.objects.filter(user=user).order_by('-started_at').prefetch_related('turns')
	session_cards = []
	chart_data = []
	status_distribution = {'completed': 0, 'active': 0, 'aborted': 0}

	for session in sessions:
		status_distribution[session.status] = status_distribution.get(session.status, 0) + 1
		turns = list(session.turns.all().order_by('turn_index'))
		turn_count = len(turns)
		avg_latency = int(sum(t.processing_ms for t in turns) / turn_count) if turn_count else 0

		quality_points = []
		latency_points = []
		labels = []
		feedback_lines = []

		for turn in turns:
			word_count = len((turn.user_transcript or '').split())
			feedback_words = len((turn.ai_feedback or '').split())
			quality = 54 + min(28, int(word_count * 1.4)) + min(10, int(feedback_words * 0.7))
			if turn.processing_ms > 0:
				quality -= min(12, int(turn.processing_ms / 850))
			quality = _clamp_score(quality)

			quality_points.append(quality)
			latency_points.append(int(turn.processing_ms))
			labels.append(f'T{turn.turn_index}')

			feedback = (turn.ai_feedback or '').strip()
			if feedback and feedback not in feedback_lines:
				feedback_lines.append(feedback)

		if quality_points:
			session_score = int(sum(quality_points) / len(quality_points))
		else:
			base_score = 58
			if session.status == InterviewSession.STATUS_COMPLETED:
				base_score += 12
			elif session.status == InterviewSession.STATUS_ABORTED:
				base_score -= 6
			session_score = _clamp_score(base_score)

		session_cards.append(
			{
				'id': session.id,
				'title': f"{session.target_company} - {session.interview_type}",
				'role': session.target_role,
				'difficulty': session.difficulty,
				'status': session.status,
				'started_at': session.started_at,
				'turn_count': turn_count,
				'avg_latency': avg_latency,
				'session_score': session_score,
				'feedback_lines': feedback_lines[:4],
				'review_text': _session_review_text(session_score, turn_count),
			}
		)

		chart_data.append(
			{
				'session_id': session.id,
				'labels': labels,
				'quality': quality_points,
				'latency': latency_points,
			}
		)

	overall_score = int(sum(item['session_score'] for item in session_cards) / len(session_cards)) if session_cards else 0

	return {
		'overall_score': overall_score,
		'session_cards': session_cards,
		'results_chart_data': chart_data,
		'status_distribution': status_distribution,
		'total_sessions': len(session_cards),
	}


def _build_feedback_context(user, requested_session_id):
	sessions = list(
		InterviewSession.objects.filter(user=user)
		.order_by('-started_at')
		.prefetch_related('turns')
	)

	if not sessions:
		return {
			'has_feedback_data': False,
			'session_options': [],
		}

	session_by_id = {str(s.id): s for s in sessions}
	selected_session = session_by_id.get(str(requested_session_id)) if requested_session_id else sessions[0]
	if selected_session is None:
		selected_session = sessions[0]

	turns = list(selected_session.turns.all().order_by('turn_index'))
	turn_count = len(turns)

	def _turn_word_count(turn):
		return len((turn.user_transcript or '').split())

	def _feedback_word_count(turn):
		return len((turn.ai_feedback or '').split())

	def _latency_penalty(turn):
		if turn.processing_ms <= 0:
			return 0
		return min(16, int(turn.processing_ms / 750))

	def _tech_hits(text):
		lower = (text or '').lower()
		keywords = [
			'architecture', 'tradeoff', 'complexity', 'latency', 'scalability',
			'cache', 'database', 'api', 'system', 'debug', 'optimization',
		]
		return sum(1 for keyword in keywords if keyword in lower)

	labels = []
	confidence_series = []
	clarity_series = []
	technical_series = []
	delivery_series = []
	feedback_lines = []

	for turn in turns:
		labels.append(f'T{turn.turn_index}')
		words = _turn_word_count(turn)
		feedback_words = _feedback_word_count(turn)
		latency_penalty = _latency_penalty(turn)
		tech_signal = _tech_hits(turn.user_transcript) + _tech_hits(turn.ai_feedback)

		confidence_series.append(_clamp_score(54 + min(26, int(words * 1.3)) - latency_penalty))
		clarity_series.append(_clamp_score(52 + min(22, int(feedback_words * 1.7)) + min(12, int(words * 0.45)) - int(latency_penalty / 2)))
		technical_series.append(_clamp_score(46 + min(30, tech_signal * 4) + min(12, turn.turn_index * 2)))
		delivery_series.append(_clamp_score(58 + min(18, int(words * 0.9)) - min(18, int(turn.processing_ms / 650)) if turn.processing_ms else 64))

		feedback = (turn.ai_feedback or '').strip()
		if feedback and feedback not in feedback_lines:
			feedback_lines.append(feedback)

	if not labels:
		labels = ['T1']
		confidence_series = [58]
		clarity_series = [61]
		technical_series = [55]
		delivery_series = [60]

	communication_score = int((sum(confidence_series) + sum(clarity_series)) / (len(confidence_series) + len(clarity_series)))
	technical_score = int(sum(technical_series) / len(technical_series))
	clarity_score = int(sum(clarity_series) / len(clarity_series))
	confidence_score = int(sum(confidence_series) / len(confidence_series))
	delivery_score = int(sum(delivery_series) / len(delivery_series))
	overall_score = int((communication_score + technical_score + clarity_score + confidence_score + delivery_score) / 5)

	category_scores = {
		'communication': communication_score,
		'technical': technical_score,
		'clarity': clarity_score,
		'confidence': confidence_score,
		'delivery': delivery_score,
	}
	strongest_key = max(category_scores, key=category_scores.get)
	weakest_key = min(category_scores, key=category_scores.get)

	nice_name = {
		'communication': 'Communication',
		'technical': 'Technical Depth',
		'clarity': 'Clarity',
		'confidence': 'Confidence',
		'delivery': 'Delivery',
	}

	coach_summary = (
		f"Strongest area: {nice_name[strongest_key]} ({category_scores[strongest_key]}/100). "
		f"Priority improvement: {nice_name[weakest_key]} ({category_scores[weakest_key]}/100). "
		"Use tighter STAR framing and explicit technical trade-offs in follow-up answers."
	)

	def _moment_label(series, mode):
		if not series:
			return 'T1'
		idx = 0
		if mode == 'max':
			idx = max(range(len(series)), key=lambda i: series[i])
		else:
			idx = min(range(len(series)), key=lambda i: series[i])
		return labels[idx]

	overview_series = {
		'confidence': confidence_series,
		'clarity': clarity_series,
	}

	focus_map = {
		'overview': {
			'confidence': overview_series['confidence'],
			'clarity': overview_series['clarity'],
			'strongest': _moment_label(overview_series['clarity'], 'max'),
			'weakest': _moment_label(overview_series['confidence'], 'min'),
		},
		'communication': {
			'confidence': [_clamp_score(v + 2) for v in confidence_series],
			'clarity': [_clamp_score(v + 3) for v in clarity_series],
			'strongest': _moment_label(clarity_series, 'max'),
			'weakest': _moment_label(clarity_series, 'min'),
		},
		'technical': {
			'confidence': [_clamp_score(v - 3) for v in technical_series],
			'clarity': technical_series,
			'strongest': _moment_label(technical_series, 'max'),
			'weakest': _moment_label(technical_series, 'min'),
		},
		'delivery': {
			'confidence': delivery_series,
			'clarity': [_clamp_score(v + 1) for v in delivery_series],
			'strongest': _moment_label(delivery_series, 'max'),
			'weakest': _moment_label(delivery_series, 'min'),
		},
	}

	recommendations = [
		{
			'key': 'communication',
			'title': 'Keep: Outcome-first framing',
			'detail': 'Lead each answer with impact first, then explain execution and trade-offs.',
			'style': 'emerald',
		},
		{
			'key': 'technical',
			'title': 'Improve: Technical specificity in follow-ups',
			'detail': 'Name one architecture decision and one rejected alternative for every technical prompt.',
			'style': 'amber',
		},
		{
			'key': 'delivery',
			'title': 'Refine: Conciseness under pressure',
			'detail': 'Keep context concise, then spend most of the time on actions, constraints, and outcomes.',
			'style': 'sky',
		},
	]

	session_options = []
	for s in sessions:
		s_turns = list(s.turns.all())
		s_avg_latency = int(sum(t.processing_ms for t in s_turns) / len(s_turns)) if s_turns else 0
		session_options.append(
			{
				'id': s.id,
				'label': f"{s.target_company} - {s.interview_type}",
				'role': s.target_role,
				'difficulty': s.difficulty,
				'status': s.status,
				'started_at': s.started_at,
				'turn_count': len(s_turns),
				'avg_latency': s_avg_latency,
			}
		)

	target_by_level = {
		'communication': 88,
		'confidence': 85,
		'technical': 86,
		'clarity': 88,
		'delivery': 84,
	}

	return {
		'has_feedback_data': True,
		'session_options': session_options,
		'selected_session': selected_session,
		'selected_session_turn_count': turn_count,
		'selected_avg_latency': int(sum(t.processing_ms for t in turns) / turn_count) if turn_count else 0,
		'overall_score': overall_score,
		'communication_score': communication_score,
		'technical_score': technical_score,
		'clarity_score': clarity_score,
		'confidence_score': confidence_score,
		'delivery_score': delivery_score,
		'strongest_area': nice_name[strongest_key],
		'weakest_area': nice_name[weakest_key],
		'coach_summary': coach_summary,
		'recommendations': recommendations,
		'feedback_lines': feedback_lines[:5],
		'trend_labels': labels,
		'radar_current': [
			communication_score,
			confidence_score,
			technical_score,
			clarity_score,
			delivery_score,
		],
		'radar_target': [
			target_by_level['communication'],
			target_by_level['confidence'],
			target_by_level['technical'],
			target_by_level['clarity'],
			target_by_level['delivery'],
		],
		'focus_payload': focus_map,
	}


def _seconds_to_clock_label(total_seconds):
	seconds = max(0, int(total_seconds or 0))
	minutes, sec = divmod(seconds, 60)
	hours, minutes = divmod(minutes, 60)
	if hours:
		return f"{hours}:{minutes:02d}:{sec:02d}"
	return f"{minutes:02d}:{sec:02d}"


def _extract_feedback_signal(feedback_text):
	text = str(feedback_text or '').strip()
	if not text:
		return {'improvement': '', 'strength': ''}

	segments = [seg.strip() for seg in re.split(r'(?<=[.!?])\s+', text) if seg.strip()]
	improvement_keywords = [
		'improve', 'could', 'should', 'missing', 'lack', 'unclear', 'weak',
		'concise', 'shorter', 'better', 'confusing', 'vague', 'overly long',
	]
	strength_keywords = [
		'strong', 'great', 'good', 'clear', 'excellent', 'effective',
		'well', 'solid', 'confident', 'structured',
	]

	improvement = ''
	strength = ''
	for segment in segments:
		lower = segment.lower()
		if not improvement and any(token in lower for token in improvement_keywords):
			improvement = segment
		if not strength and any(token in lower for token in strength_keywords):
			strength = segment
		if improvement and strength:
			break

	return {'improvement': improvement, 'strength': strength}


def _build_replay_context(request, user, requested_session_id):
	sessions = list(
		InterviewSession.objects.filter(user=user)
		.order_by('-started_at')
		.prefetch_related('turns')
	)

	if not sessions:
		return {
			'has_replay_data': False,
			'session_options': [],
			'impact_categories': [],
			'impact_values': [],
		}

	session_by_id = {str(s.id): s for s in sessions}
	selected_session = session_by_id.get(str(requested_session_id)) if requested_session_id else sessions[0]
	if selected_session is None:
		selected_session = sessions[0]

	turns = list(selected_session.turns.all().order_by('turn_index'))
	if not turns:
		return {
			'has_replay_data': False,
			'session_options': [
				{
					'id': str(s.id),
					'label': f"{s.target_company} | {s.target_role} | {timezone.localtime(s.started_at).strftime('%b %d, %Y')}",
				}
				for s in sessions
			],
			'impact_categories': [],
			'impact_values': [],
		}

	base_time = turns[0].created_at
	last_time = turns[-1].created_at
	duration_seconds = max(30, int((last_time - base_time).total_seconds()) + 45)

	replay_rows = []
	replay_markers = []
	evidence_cards = []
	strength_hits = 0
	improvement_hits = 0
	user_word_total = 0

	for turn in turns:
		relative_seconds = max(0, int((turn.created_at - base_time).total_seconds()))
		time_label = _seconds_to_clock_label(relative_seconds)
		user_text = str(turn.user_transcript or '').strip()
		ai_text = str(turn.ai_response or '').strip()
		feedback = str(turn.ai_feedback or '').strip()
		signal = _extract_feedback_signal(feedback)

		if signal['improvement']:
			marker_tone = 'warn'
			improvement_hits += 1
		elif signal['strength']:
			marker_tone = 'good'
			strength_hits += 1
		else:
			marker_tone = 'neutral'

		if user_text:
			user_word_total += len(user_text.split())

		ai_audio_url = _build_media_url(request, turn.ai_audio_path) if turn.ai_audio_path else ''
		replay_rows.append(
			{
				'turn_index': turn.turn_index,
				'time_label': time_label,
				'relative_seconds': relative_seconds,
				'user_text': user_text or ai_text or 'No transcript available for this turn.',
				'ai_prompt': ai_text or 'No AI prompt captured.',
				'feedback': feedback,
				'marker_tone': marker_tone,
				'ai_audio_url': ai_audio_url,
			}
		)

		replay_markers.append(
			{
				'time_label': time_label,
				'relative_seconds': relative_seconds,
				'marker_tone': marker_tone,
				'ai_audio_url': ai_audio_url,
			}
		)

		if signal['improvement']:
			evidence_cards.append(
				{
					'tone': 'improve',
					'time_label': time_label,
					'title': 'Improve Here',
					'detail': signal['improvement'],
				}
			)
		if signal['strength']:
			evidence_cards.append(
				{
					'tone': 'good',
					'time_label': time_label,
					'title': 'Strong Moment',
					'detail': signal['strength'],
				}
			)

	if not evidence_cards:
		evidence_cards.append(
			{
				'tone': 'neutral',
				'time_label': _seconds_to_clock_label(0),
				'title': 'Replay Insight',
				'detail': 'Feedback markers will appear as turns are captured with AI feedback.',
			}
		)

	avg_words = int(user_word_total / max(1, len(turns)))
	communication_score = _clamp_score(56 + min(22, int(avg_words * 0.9)) + strength_hits * 2 - improvement_hits * 2)
	clarity_score = _clamp_score(60 + strength_hits * 3 - improvement_hits * 3)
	confidence_score = _clamp_score(58 + strength_hits * 2 - improvement_hits * 2)

	active_marker = replay_markers[min(len(replay_markers) - 1, max(0, len(replay_markers) // 2))]

	return {
		'has_replay_data': True,
		'session_options': [
			{
				'id': str(s.id),
				'label': f"{s.target_company} | {s.target_role} | {timezone.localtime(s.started_at).strftime('%b %d, %Y')}",
			}
			for s in sessions
		],
		'selected_session_id': str(selected_session.id),
		'selected_session': selected_session,
		'session_title': f"{selected_session.target_company} {selected_session.target_role}",
		'session_subtitle': f"{selected_session.interview_type} | {selected_session.difficulty}",
		'replay_duration_seconds': duration_seconds,
		'replay_duration_label': _seconds_to_clock_label(duration_seconds),
		'replay_active_time': active_marker['time_label'],
		'replay_active_seconds': active_marker['relative_seconds'],
		'replay_rows': replay_rows,
		'replay_markers': replay_markers,
		'replay_evidence': evidence_cards[:8],
		'impact_categories': ['Communication', 'Clarity', 'Confidence'],
		'impact_values': [communication_score, clarity_score, confidence_score],
	}


def _normalize_company_name(raw_company: str) -> str:
	return ' '.join((raw_company or '').strip().split())


def _load_company_names_from_repo() -> list:
	if _CODING_COMPANY_CACHE.get('loaded'):
		return _CODING_COMPANY_CACHE.get('names', [])

	api_url = 'https://api.github.com/repos/liquidslr/interview-company-wise-problems/git/trees/main?recursive=1'
	headers = {'User-Agent': 'TalvoAI'}
	company_names = set()

	try:
		response = requests.get(api_url, headers=headers, timeout=20)
		response.raise_for_status()
		payload = response.json() if response.content else {}
		for node in payload.get('tree', []):
			path = str(node.get('path', '') or '')
			if '/' not in path:
				continue
			parts = path.split('/')
			if len(parts) >= 2 and parts[1].endswith('.csv'):
				company_names.add(parts[0])
	except Exception:
		company_names = {'Google', 'Amazon', 'Microsoft', 'Meta', 'Adobe'}

	names = sorted(company_names)
	_CODING_COMPANY_CACHE['names'] = names
	_CODING_COMPANY_CACHE['loaded'] = True
	return names


def _resolve_repo_company(target_company: str) -> str:
	normalized = _normalize_company_name(target_company).lower()
	companies = _load_company_names_from_repo()
	if not companies:
		return 'Google'

	for name in companies:
		if name.lower() == normalized:
			return name

	for name in companies:
		lower = name.lower()
		if normalized and (normalized in lower or lower in normalized):
			return name

	return 'Google'


def _load_company_questions(company: str) -> list:
	resolved = _resolve_repo_company(company)
	rows = []
	try:
		raw_url = f"https://raw.githubusercontent.com/liquidslr/interview-company-wise-problems/main/{quote(resolved)}/5.%20All.csv"
		response = requests.get(raw_url, timeout=6)
		response.raise_for_status()
		reader = csv.DictReader(io.StringIO(response.text))
		for row in reader:
			title = str(row.get('Title', '') or '').strip()
			if not title:
				continue
			try:
				frequency = float(row.get('Frequency', 0) or 0)
			except Exception:
				frequency = 0.0
			try:
				acceptance_rate = float(row.get('Acceptance Rate', 0) or 0)
			except Exception:
				acceptance_rate = 0.0
			rows.append(
				{
					'title': title,
					'difficulty': str(row.get('Difficulty', 'Medium') or 'Medium').strip().title(),
					'frequency': frequency,
					'acceptance_rate': acceptance_rate,
					'link': str(row.get('Link', '') or '').strip(),
					'topics': str(row.get('Topics', '') or '').strip(),
					'company': resolved,
				}
			)
		rows.sort(key=lambda item: item.get('frequency', 0), reverse=True)
	except Exception:
		pass

	if not rows:
		rows = [
			{
				'title': 'Two Sum',
				'difficulty': 'Easy',
				'frequency': 100.0,
				'acceptance_rate': 52.4,
				'link': 'https://leetcode.com/problems/two-sum/',
				'topics': 'Array, Hash Table',
				'company': resolved or 'Google',
			},
			{
				'title': 'Valid Anagram',
				'difficulty': 'Easy',
				'frequency': 95.0,
				'acceptance_rate': 64.1,
				'link': 'https://leetcode.com/problems/valid-anagram/',
				'topics': 'Hash Table, String',
				'company': resolved or 'Google',
			},
			{
				'title': 'Reverse Linked List',
				'difficulty': 'Easy',
				'frequency': 90.0,
				'acceptance_rate': 76.2,
				'link': 'https://leetcode.com/problems/reverse-linked-list/',
				'topics': 'Linked List',
				'company': resolved or 'Google',
			},
			{
				'title': 'Container With Most Water',
				'difficulty': 'Medium',
				'frequency': 85.0,
				'acceptance_rate': 55.0,
				'link': 'https://leetcode.com/problems/container-with-most-water/',
				'topics': 'Array, Two Pointers',
				'company': resolved or 'Google',
			},
			{
				'title': 'Merge Intervals',
				'difficulty': 'Medium',
				'frequency': 82.0,
				'acceptance_rate': 47.1,
				'link': 'https://leetcode.com/problems/merge-intervals/',
				'topics': 'Array, Sorting',
				'company': resolved or 'Google',
			},
		]

	return rows


def _safe_json_loads(raw_text: str):
	if not isinstance(raw_text, str):
		return None

	text = raw_text.strip()
	if not text:
		return None

	candidates = [text]
	if '```' in text:
		without_fences = text.replace('```json', '').replace('```JSON', '').replace('```', '').strip()
		if without_fences:
			candidates.append(without_fences)

	for candidate in list(candidates):
		start = candidate.find('{')
		end = candidate.rfind('}')
		if start >= 0 and end > start:
			candidates.append(candidate[start : end + 1])

	seen = set()
	for candidate in candidates:
		if candidate in seen:
			continue
		seen.add(candidate)
		try:
			return json.loads(candidate)
		except Exception:
			continue

	return None


def _normalize_tests(raw_tests, max_count: int, default_tests: list) -> list:
	if not isinstance(raw_tests, list):
		return default_tests[:max_count]

	normalized = []
	for test in raw_tests:
		if not isinstance(test, dict):
			continue
		if 'expected' not in test:
			continue
		args = test.get('args', [])
		kwargs = test.get('kwargs', {})
		if not isinstance(args, list):
			args = [args]
		if not isinstance(kwargs, dict):
			kwargs = {}
		normalized.append(
			{
				'args': args,
				'kwargs': kwargs,
				'expected': test.get('expected'),
			}
		)
		if len(normalized) >= max_count:
			break

	if not normalized:
		return default_tests[:max_count]
	return normalized


LEETCODE_PRESET_PACKS = {
	'two sum': {
		'prompt': 'Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.',
		'function_name': 'twoSum',
		'starter_code': (
			"class Solution:\n"
			"    def twoSum(self, nums: list[int], target: int) -> list[int]:\n"
			"        # Write your solution here\n"
			"        pass\n"
		),
		'constraints': '• 2 <= nums.length <= 10^4\n• -10^9 <= nums[i] <= 10^9\n• -10^9 <= target <= 10^9\n• Only one valid answer exists.',
		'visible_tests': [
			{'args': [[2, 7, 11, 15], 9], 'expected': [0, 1]},
			{'args': [[3, 2, 4], 6], 'expected': [1, 2]},
			{'args': [[3, 3], 6], 'expected': [0, 1]},
		],
		'hidden_tests': [
			{'args': [[1, 5, 8, 10], 13], 'expected': [1, 2]},
			{'args': [[-1, -8, 0, 5, 7], 6], 'expected': [0, 4]},
			{'args': [[11, 15, 2, 7], 9], 'expected': [2, 3]},
		],
	},
	'valid anagram': {
		'prompt': 'Given two strings `s` and `t`, return `True` if `t` is an anagram of `s`, and `False` otherwise.\n\nAn Anagram is a word or phrase formed by rearranging the letters of a different word or phrase.',
		'function_name': 'isAnagram',
		'starter_code': (
			"class Solution:\n"
			"    def isAnagram(self, s: str, t: str) -> bool:\n"
			"        # Write your solution here\n"
			"        pass\n"
		),
		'constraints': '• 1 <= s.length, t.length <= 5 * 10^4\n• s and t consist of lowercase English letters.',
		'visible_tests': [
			{'args': ['anagram', 'nagaram'], 'expected': True},
			{'args': ['rat', 'car'], 'expected': False},
			{'args': ['listen', 'silent'], 'expected': True},
		],
		'hidden_tests': [
			{'args': ['a', 'ab'], 'expected': False},
			{'args': ['aacc', 'ccac'], 'expected': False},
			{'args': ['fluster', 'restful'], 'expected': True},
		],
	},
	'reverse linked list': {
		'prompt': 'Given the head of a singly linked list represented as an array of integers, reverse the list and return the reversed list as an array.',
		'function_name': 'reverseList',
		'starter_code': (
			"class Solution:\n"
			"    def reverseList(self, head: list[int]) -> list[int]:\n"
			"        # Write your solution here\n"
			"        pass\n"
		),
		'constraints': '• The number of nodes in the list is in the range [0, 5000].\n• -5000 <= Node.val <= 5000',
		'visible_tests': [
			{'args': [[1, 2, 3, 4, 5]], 'expected': [5, 4, 3, 2, 1]},
			{'args': [[1, 2]], 'expected': [2, 1]},
			{'args': [[]], 'expected': []},
		],
		'hidden_tests': [
			{'args': [[10]], 'expected': [10]},
			{'args': [[1, 2, 3]], 'expected': [3, 2, 1]},
		],
	},
	'container with most water': {
		'prompt': 'Given an integer array `height` of length `n`. Find two lines that together with the x-axis form a container that contains the most water.\n\nReturn the maximum amount of water a container can store.',
		'function_name': 'maxArea',
		'starter_code': (
			"class Solution:\n"
			"    def maxArea(self, height: list[int]) -> int:\n"
			"        # Write your solution here\n"
			"        pass\n"
		),
		'constraints': '• n == height.length\n• 2 <= n <= 10^5\n• 0 <= height[i] <= 10^4',
		'visible_tests': [
			{'args': [[1, 8, 6, 2, 5, 4, 8, 3, 7]], 'expected': 49},
			{'args': [[1, 1]], 'expected': 1},
		],
		'hidden_tests': [
			{'args': [[4, 3, 2, 1, 4]], 'expected': 16},
			{'args': [[1, 2, 1]], 'expected': 2},
		],
	},
	'merge intervals': {
		'prompt': 'Given an array of `intervals` where `intervals[i] = [start_i, end_i]`, merge all overlapping intervals, and return an array of the non-overlapping intervals.',
		'function_name': 'merge',
		'starter_code': (
			"class Solution:\n"
			"    def merge(self, intervals: list[list[int]]) -> list[list[int]]:\n"
			"        # Write your solution here\n"
			"        pass\n"
		),
		'constraints': '• 1 <= intervals.length <= 10^4\n• 0 <= start_i <= end_i <= 10^4',
		'visible_tests': [
			{'args': [[[1, 3], [2, 6], [8, 10], [15, 18]]], 'expected': [[1, 6], [8, 10], [15, 18]]},
			{'args': [[[1, 4], [4, 5]]], 'expected': [[1, 5]]},
		],
		'hidden_tests': [
			{'args': [[[1, 4], [2, 3]]], 'expected': [[1, 4]]},
			{'args': [[[1, 4], [0, 4]]], 'expected': [[0, 4]]},
		],
	},
}


def _build_leetcode_starter_code(title: str, function_name: str = '', visible_tests: list = None) -> str:
	title_text = str(title or '').strip()
	fn_name = function_name.strip() if (function_name and function_name != 'solve' and function_name.isidentifier()) else _title_to_function_name(title_text)
	if not fn_name.isidentifier() or fn_name == 'solve':
		fn_name = _title_to_function_name(title_text)

	sample_args = visible_tests[0].get('args', []) if (visible_tests and len(visible_tests) > 0 and isinstance(visible_tests[0], dict)) else []

	param_specs = []
	if isinstance(sample_args, list) and len(sample_args) > 0:
		for idx, arg in enumerate(sample_args):
			pname = f"arg{idx+1}"
			ptype = ""
			if isinstance(arg, list):
				if arg and isinstance(arg[0], list):
					ptype = ": list[list[int]]"
					pname = "matrix" if idx == 0 else "intervals"
				else:
					ptype = ": list[int]"
					pname = "nums" if idx == 0 else f"list{idx+1}"
			elif isinstance(arg, str):
				ptype = ": str"
				pname = "s" if idx == 0 else ("t" if idx == 1 else f"str{idx+1}")
			elif isinstance(arg, int):
				ptype = ": int"
				pname = "target" if idx == 1 else ("val" if idx == 0 else f"n{idx+1}")
			elif isinstance(arg, bool):
				ptype = ": bool"
				pname = "flag"
			param_specs.append(f"{pname}{ptype}")
	else:
		title_lower = title_text.lower()
		if 'two sum' in title_lower or 'sum' in title_lower:
			param_specs = ["nums: list[int]", "target: int"]
		elif 'string' in title_lower or 'anagram' in title_lower or 'parenthes' in title_lower:
			param_specs = ["s: str"]
		elif 'linked' in title_lower or 'list' in title_lower:
			param_specs = ["head: list[int]"]
		else:
			param_specs = ["nums: list[int]"]

	params_str = ", ".join(["self"] + param_specs)
	return (
		"class Solution:\n"
		f"    def {fn_name}({params_str}):\n"
		"        # Write your solution here\n"
		"        pass\n"
	)


def _should_offer_coding_ide(question_text: str, interview_type: str = '') -> bool:
	text = str(question_text or '').strip().lower()
	if not text:
		return False

	interview_type_text = str(interview_type or '').strip().lower()
	if interview_type_text in {'technical coding', 'technical round'}:
		return True
	if interview_type_text in {'final round', 'final'}:
		return False
	if interview_type_text in {'behavioral', 'hr'}:
		return False

	challenge_signals = [
		r'\bsolve\b',
		r'\bimplement\b',
		r'\bwrite\s+(a|an|the)?\s*function\b',
		r'\bcode\b',
		r'\bpseudocode\b',
		r'\bleetcode\b',
		r'\breturn\b.*\bgiven\b',
	]

	coding_nouns = [
		r'\barray\b',
		r'\bstring\b',
		r'\blinked\s*list\b',
		r'\btree\b',
		r'\bgraph\b',
		r'\bhash\s*map\b',
		r'\bstack\b',
		r'\bqueue\b',
		r'\btime\s+complexity\b',
		r'\bspace\s+complexity\b',
	]

	has_challenge_signal = any(re.search(pattern, text) for pattern in challenge_signals)
	has_coding_noun = any(re.search(pattern, text) for pattern in coding_nouns)

	if has_challenge_signal and has_coding_noun:
		return True

	return bool(re.search(r'\b(given|input|output|constraints)\b', text) and re.search(r'\bfunction\b', text))


def _choose_question_with_llm(session: InterviewSession, candidates: list) -> dict:
	if not candidates:
		return {}

	pipeline = InterviewPipeline.instance()
	try:
		pipeline._ensure_models()
		model_name = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant')
		shortlist = candidates[:25]
		lines = []
		for idx, item in enumerate(shortlist):
			lines.append(
				f"{idx}: {item['title']} | {item['difficulty']} | topics={item['topics']} | freq={item['frequency']}"
			)

		prompt = (
			"Select exactly one coding interview question for a live session. "
			"Prefer practical software engineering relevance and difficulty fit.\n"
			f"Company: {session.target_company}\n"
			f"Role: {session.target_role}\n"
			f"Difficulty preference: {session.difficulty}\n"
			"Candidates:\n"
			+ "\n".join(lines)
			+ "\nReturn only a raw JSON object with this schema: {\"index\": <int>, \"reason\": \"<short reason>\"}."
		)

		resp = pipeline._groq.chat.completions.create(
			model=model_name,
			temperature=0.2,
			max_tokens=120,
			messages=[
				{'role': 'system', 'content': 'You are a technical interviewer selecting one coding problem.'},
				{'role': 'user', 'content': prompt},
			],
		)

		raw = (resp.choices[0].message.content or '').strip()
		parsed = _safe_json_loads(raw) or {}
		idx = int(parsed.get('index', 0)) if isinstance(parsed, dict) else 0
		if idx < 0 or idx >= len(shortlist):
			idx = 0
		chosen = dict(shortlist[idx])
		chosen['selection_reason'] = str(parsed.get('reason', '') or 'Selected for interview relevance and balanced difficulty.')
		return chosen
	except Exception:
		fallback = dict(random.choice(candidates[: min(10, len(candidates))]))
		fallback['selection_reason'] = 'Selected from top-frequency company questions for this prototype session.'
		return fallback


def _build_python_pack_with_llm(question_item: dict) -> dict:
	title_lower = str(question_item.get('title', '') or '').strip().lower()
	for key in LEETCODE_PRESET_PACKS:
		if key in title_lower or title_lower in key:
			return dict(LEETCODE_PRESET_PACKS[key])

	pipeline = InterviewPipeline.instance()
	try:
		pipeline._ensure_models()
		model_name = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant')
		prompt = (
			"Create a Python coding evaluator pack for this LeetCode-style problem title.\n"
			f"Title: {question_item.get('title', '')}\n"
			f"Difficulty: {question_item.get('difficulty', 'Medium')}\n"
			f"Topics: {question_item.get('topics', '')}\n"
			"Return strict JSON only with keys: "
			"prompt, function_name, starter_code, constraints, visible_tests, hidden_tests.\n"
			"starter_code MUST be a Python class Solution template (e.g. 'class Solution:\\n    def functionName(self, arg1: type, arg2: type) -> return_type:\\n        pass').\n"
			"Each test must be JSON object {args: [...], expected: <json value>}.\n"
			"Use 3 visible_tests and 5 hidden_tests. Return only raw JSON, no markdown fences."
		)

		resp = pipeline._groq.chat.completions.create(
			model=model_name,
			temperature=0.2,
			max_tokens=900,
			messages=[
				{'role': 'system', 'content': 'Generate safe, deterministic Python function tasks with JSON-only response.'},
				{'role': 'user', 'content': prompt},
			],
		)

		raw = (resp.choices[0].message.content or '').strip()
		parsed = _safe_json_loads(raw)
		if not isinstance(parsed, dict):
			raise ValueError('Invalid coding pack JSON')

		function_name = str(parsed.get('function_name', '') or '').strip()
		if not function_name or not function_name.isidentifier() or function_name == 'solve':
			function_name = _title_to_function_name(question_item.get('title', ''))

		visible_defaults = [
			{'args': [[2, 7, 11, 15], 9], 'expected': [0, 1]},
			{'args': [[3, 2, 4], 6], 'expected': [1, 2]},
		]
		hidden_defaults = [
			{'args': [[3, 3], 6], 'expected': [0, 1]},
			{'args': [[1, 5, 8, 10], 13], 'expected': [1, 2]},
		]
		visible = _normalize_tests(parsed.get('visible_tests'), 4, visible_defaults)
		hidden = _normalize_tests(parsed.get('hidden_tests'), 8, hidden_defaults)

		raw_starter = str(parsed.get('starter_code', '') or '').strip()
		if raw_starter and ('def ' in raw_starter or 'class ' in raw_starter) and '*args, **kwargs' not in raw_starter and 'solve(' not in raw_starter:
			starter_code = raw_starter
		else:
			starter_code = _build_leetcode_starter_code(question_item.get('title', ''), function_name, visible)

		return {
			'prompt': str(parsed.get('prompt', '') or question_item.get('title', 'Solve the coding question.')),
			'function_name': function_name,
			'starter_code': starter_code,
			'constraints': str(parsed.get('constraints', '') or ''),
			'visible_tests': visible[:4],
			'hidden_tests': hidden[:8],
		}
	except Exception:
		fn_name = _title_to_function_name(question_item.get('title', ''))
		visible_tests = [
			{'args': [[2, 7, 11, 15], 9], 'expected': [0, 1]},
			{'args': [[3, 2, 4], 6], 'expected': [1, 2]},
		]
		return {
			'prompt': f"Implement a solution for: {question_item.get('title', 'Coding Problem')}.",
			'function_name': fn_name,
			'starter_code': _build_leetcode_starter_code(question_item.get('title', ''), fn_name, visible_tests),
			'constraints': 'Return deterministic output for all visible and hidden test cases.',
			'visible_tests': visible_tests,
			'hidden_tests': [
				{'args': [[3, 3], 6], 'expected': [0, 1]},
			],
		}


def _run_python_evaluator(source_code: str, function_name: str, tests: list) -> dict:
	if len(source_code or '') > 50000:
		return {'ok': False, 'error': 'Source code too large. Keep code under 50k characters.'}

	harness = textwrap.dedent(
		f"""
		import json

		tests = {json.dumps(tests)}
		function_name = {json.dumps(function_name)}

		namespace = {{}}
		try:
			exec(compile({json.dumps(source_code)}, '<candidate>', 'exec'), namespace)
		except Exception as exc:
			print(json.dumps({{'ok': False, 'error': f'Compilation error: {{exc}}'}}))
			raise SystemExit(0)

		fn = namespace.get(function_name)

		# Support LeetCode `class Solution:` style
		if not callable(fn) and 'Solution' in namespace:
			sol_cls = namespace['Solution']
			try:
				instance = sol_cls()
				fn = getattr(instance, function_name, None)
			except Exception:
				pass

		if not callable(fn):
			print(json.dumps({{'ok': False, 'error': f"Function or Solution method '{{function_name}}' not found. Ensure method name is '{{function_name}}'."}}))
			raise SystemExit(0)

		results = []
		for idx, test in enumerate(tests, start=1):
			args = test.get('args', [])
			kwargs = test.get('kwargs', {{}})
			expected = test.get('expected')
			try:
				actual = fn(*args, **kwargs)
				passed = actual == expected
				results.append({{
					'index': idx,
					'passed': passed,
					'expected': expected,
					'actual': actual,
				}})
			except Exception as exc:
				results.append({{
					'index': idx,
					'passed': False,
					'error': str(exc),
				}})

		passed_count = sum(1 for item in results if item.get('passed'))
		print(json.dumps({{
			'ok': True,
			'passed_count': passed_count,
			'total_count': len(results),
			'results': results,
		}}))
		"""
	)

	with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as handle:
		handle.write(harness)
		temp_path = handle.name

	try:
		completed = subprocess.run(
			[sys.executable, '-I', temp_path],
			capture_output=True,
			text=True,
			timeout=4,
		)
		if completed.returncode != 0 and not completed.stdout:
			return {'ok': False, 'error': (completed.stderr or 'Execution failed').strip()}

		payload = _safe_json_loads((completed.stdout or '').strip())
		if not isinstance(payload, dict):
			return {'ok': False, 'error': 'Evaluator returned invalid output.'}
		return payload
	except subprocess.TimeoutExpired:
		return {'ok': False, 'error': 'Execution timed out (limit: 4 seconds).'}
	except Exception as exc:
		return {'ok': False, 'error': f'Evaluator failed: {exc}'}
	finally:
		try:
			Path(temp_path).unlink(missing_ok=True)
		except Exception:
			pass


def _run_python_output(source_code: str) -> dict:
	if len(source_code or '') > 50000:
		return {'ok': False, 'error': 'Source code too large. Keep code under 50k characters.'}

	with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as handle:
		handle.write(source_code)
		temp_path = handle.name

	try:
		completed = subprocess.run(
			[sys.executable, '-I', temp_path],
			capture_output=True,
			text=True,
			timeout=4,
		)
		return {
			'ok': completed.returncode == 0,
			'returncode': completed.returncode,
			'stdout': (completed.stdout or '').strip(),
			'stderr': (completed.stderr or '').strip(),
		}
	except subprocess.TimeoutExpired:
		return {'ok': False, 'error': 'Execution timed out (limit: 4 seconds).'}
	except Exception as exc:
		return {'ok': False, 'error': f'Run failed: {exc}'}
	finally:
		try:
			Path(temp_path).unlink(missing_ok=True)
		except Exception:
			pass


def _get_or_create_coding_pack(session: InterviewSession) -> dict:
	key = str(session.id)
	if key in _CODING_SESSION_PACKS:
		cached = _CODING_SESSION_PACKS[key]
		if '*args, **kwargs' in cached.get('starter_code', '') or cached.get('function_name') == 'solve':
			fn_name = cached.get('function_name', '')
			if not fn_name or fn_name == 'solve':
				fn_name = _title_to_function_name(cached.get('title', ''))
				cached['function_name'] = fn_name
			cached['starter_code'] = _build_leetcode_starter_code(cached.get('title', ''), fn_name, cached.get('visible_tests', []))
		return cached

	try:
		candidates = _load_company_questions(session.target_company)
	except Exception:
		candidates = []

	if not candidates:
		candidates = [
			{
				'title': 'Two Sum',
				'difficulty': session.difficulty or 'Medium',
				'frequency': 100.0,
				'acceptance_rate': 52.4,
				'link': 'https://leetcode.com/problems/two-sum/',
				'topics': 'Array, Hash Table',
				'company': session.target_company or 'Google',
			}
		]

	try:
		chosen = _choose_question_with_llm(session, candidates)
		pack = _build_python_pack_with_llm(chosen)
	except Exception:
		chosen = candidates[0]
		pack = _build_python_pack_with_llm(chosen)

	final_function_name = pack.get('function_name', '')
	if not final_function_name or final_function_name == 'solve':
		final_function_name = _title_to_function_name(chosen.get('title', ''))

	final_starter_code = pack.get('starter_code', '')
	if not final_starter_code or '*args, **kwargs' in final_starter_code or 'solve(' in final_starter_code:
		final_starter_code = _build_leetcode_starter_code(chosen.get('title', ''), final_function_name, pack.get('visible_tests', []))

	final_pack = {
		'session_id': session.id,
		'company': chosen.get('company', session.target_company),
		'difficulty': chosen.get('difficulty', session.difficulty),
		'title': chosen.get('title', 'Coding Problem'),
		'link': chosen.get('link', ''),
		'topics': chosen.get('topics', ''),
		'selection_reason': chosen.get('selection_reason', 'AI selected this coding prompt for your current interview context.'),
		'prompt': pack.get('prompt', ''),
		'constraints': pack.get('constraints', ''),
		'function_name': final_function_name,
		'starter_code': final_starter_code,
		'visible_tests': pack.get('visible_tests', []),
		'hidden_tests': pack.get('hidden_tests', []),
	}
	_CODING_SESSION_PACKS[key] = final_pack
	return final_pack


def _build_code_analysis_summary(source_code: str) -> str:
	text = str(source_code or '')
	lower = text.lower()
	lines = [ln for ln in text.splitlines() if ln.strip()]

	has_dict = 'dict' in lower or '{}' in text
	has_set = 'set(' in lower or ' set ' in lower
	has_sort = '.sort(' in lower or 'sorted(' in lower
	has_recursion = False
	has_nested_loop = bool(re.search(r'for\s+.+:\s*\n\s+for\s+', text)) or text.count('for ') >= 2

	function_names = []
	try:
		tree = ast.parse(text)
		for node in ast.walk(tree):
			if isinstance(node, ast.FunctionDef):
				function_names.append(node.name)
		for node in ast.walk(tree):
			if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in function_names:
				has_recursion = True
				break
	except Exception:
		pass

	signals = []
	if has_nested_loop:
		signals.append('uses nested iteration')
	if has_dict:
		signals.append('uses hash-map/dict lookups')
	if has_set:
		signals.append('uses set membership checks')
	if has_sort:
		signals.append('uses sorting as part of the approach')
	if has_recursion:
		signals.append('uses recursion')
	if not signals:
		signals.append('uses a straightforward iterative approach')

	return f"approx_lines={len(lines)}; " + ', '.join(signals)


def _build_fallback_code_followups(pack: dict, source_code: str, all_passed: bool, failed_tests: list) -> list:
	prompt = str(pack.get('prompt', '') or '').strip()
	analysis = _build_code_analysis_summary(source_code)
	questions = []

	questions.append(
		f"Walk me through your algorithm for this problem. Why is this approach correct for all valid inputs?"
	)

	if 'nested iteration' in analysis and 'hash-map/dict' not in analysis:
		questions.append(
			"Your code appears to use nested loops. How would you optimize it to reduce time complexity, and what data structure would you use?"
		)
	elif 'hash-map/dict' in analysis:
		questions.append(
			"You used a hash-map style approach. Explain the average and worst-case complexity, and when this can degrade in practice."
		)
	elif 'sorting' in analysis:
		questions.append(
			"You used sorting in your solution. Why is sorting appropriate here, and what trade-off does it introduce versus linear-time methods?"
		)
	else:
		questions.append(
			"What is the time and space complexity of your current solution, and what specific change would improve one of them?"
		)

	if all_passed:
		questions.append(
			"If constraints were 100x larger, what algorithmic changes would you make to keep latency low?"
		)
	else:
		err = ''
		if failed_tests:
			first_fail = failed_tests[0] if isinstance(failed_tests[0], dict) else {}
			err = str(first_fail.get('error') or '')
		questions.append(
			"A few tests failed. Which edge case did your logic miss, and how would you modify your algorithm to handle it reliably?"
		)
		if err:
			questions.append(f"One failure indicates: '{err}'. What part of your code likely causes this, and how would you debug it quickly?")

	questions.append(
		f"For this prompt: '{prompt[:140]}', propose one alternative algorithm and compare its complexity and implementation risk with your current solution."
	)

	clean = []
	seen = set()
	for q in questions:
		text = str(q or '').strip()
		if not text:
			continue
		if text in seen:
			continue
		seen.add(text)
		clean.append(text)
	return clean[:5]


def _build_code_followup_questions_with_llm(session: InterviewSession, pack: dict, source_code: str, all_passed: bool, failed_tests: list) -> list:
	analysis = _build_code_analysis_summary(source_code)
	fail_summary = []
	for item in (failed_tests or [])[:3]:
		if not isinstance(item, dict):
			continue
		fail_summary.append(
			{
				'index': item.get('index'),
				'error': item.get('error', ''),
				'expected': item.get('expected'),
				'actual': item.get('actual'),
			}
		)

	try:
		pipeline = InterviewPipeline.instance()
		pipeline._ensure_models()
		model_name = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant')
		prompt = (
			"You are a senior software interviewer. Based on the candidate's submitted code, generate code-aware follow-up interview questions.\n"
			f"Role: {session.target_role}\n"
			f"Company: {session.target_company}\n"
			f"Difficulty: {session.difficulty}\n"
			f"Problem title: {pack.get('title', '')}\n"
			f"Problem prompt: {pack.get('prompt', '')}\n"
			f"Code analysis signals: {analysis}\n"
			f"All tests passed: {bool(all_passed)}\n"
			f"Failed test summary: {json.dumps(fail_summary)}\n"
			"Candidate source code:\n"
			f"{source_code[:4500]}\n"
			"Return JSON only: {\"questions\": [\"q1\", \"q2\", \"q3\", ...]}.\n"
			"Rules: Ask 4 concise follow-ups. Focus on algorithm complexity, correctness, edge cases, trade-offs, and debugging decisions from this exact code."
		)

		resp = pipeline._groq.chat.completions.create(
			model=model_name,
			temperature=0.35,
			max_tokens=350,
			messages=[
				{'role': 'system', 'content': 'Ask code-specific interview follow-up questions in JSON.'},
				{'role': 'user', 'content': prompt},
			],
		)

		raw = (resp.choices[0].message.content or '').strip()
		parsed = _safe_json_loads(raw) or {}
		questions = parsed.get('questions') if isinstance(parsed, dict) else None
		if isinstance(questions, list):
			clean = [str(q or '').strip() for q in questions if str(q or '').strip()]
			if clean:
				return clean[:5]
	except Exception:
		pass

	return _build_fallback_code_followups(pack, source_code, all_passed, failed_tests)


def _activate_code_followup_mode(session: InterviewSession, pack: dict, source_code: str, all_passed: bool, failed_tests: list) -> dict:
	questions = _build_code_followup_questions_with_llm(session, pack, source_code, all_passed, failed_tests)
	state = {
		'questions': questions,
		'next_index': 1 if questions else 0,
		'source_summary': _build_code_analysis_summary(source_code),
		'active': bool(questions),
	}
	_CODING_FOLLOWUP_STATE[str(session.id)] = state
	return {
		'enabled': bool(questions),
		'first_question': questions[0] if questions else '',
		'remaining_count': max(0, len(questions) - 1),
	}


@login_required
@require_POST
def live_interview_start_api(request):
	try:
		payload = json.loads(request.body.decode('utf-8') or '{}')
	except json.JSONDecodeError:
		return JsonResponse({'ok': False, 'error': 'Invalid JSON payload'}, status=400)

	target_role = (payload.get('target_role') or '').strip() or 'Software Engineer'
	target_company = (payload.get('target_company') or '').strip() or 'Google'
	difficulty = (payload.get('difficulty') or '').strip() or 'Medium'
	include_resume = _as_bool(payload.get('include_resume', False))
	round = (payload.get('round') or '').strip().lower()
	if round == 'final':
		interview_type = 'Final Round'
	elif round == 'technical':
		interview_type = 'Technical Coding'
	else:
		interview_type = (payload.get('interview_type') or '').strip() or 'Technical'
	target_role, interview_type = _enforce_software_focus(target_role, interview_type)

	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	resume_text = _refresh_resume_text_from_saved_file(profile)
	has_resume = bool(resume_text or profile.resume_file)
	if include_resume and (round == 'final' or interview_type.lower() == 'final round') and not has_resume:
		return JsonResponse(
			{
				'ok': False,
				'error': 'Resume not added. Please upload your resume first in Settings tab.',
			},
			status=400,
		)

	if include_resume and (round == 'final' or interview_type.lower() == 'final round') and not resume_text:
		return JsonResponse(
			{
				'ok': False,
				'error': 'Resume file found but text extraction failed. Re-upload a text-readable PDF/DOCX/TXT from Settings.',
			},
			status=400,
		)

	resume_context = _build_resume_context_blob(resume_text) if include_resume else ''
	if not include_resume:
		resume_context = ''
	candidate_name = _resolve_candidate_name(user=request.user, include_resume=include_resume, resume_text=resume_text)

	session = InterviewSession.objects.create(
		user=request.user,
		target_role=target_role,
		target_company=target_company,
		difficulty=difficulty,
		interview_type=interview_type,
		include_resume=bool(include_resume),
		resume_context=resume_context,
	)

	_, ai_rel = _build_audio_paths(session, 1)
	pipeline = InterviewPipeline.instance()

	try:
		result = pipeline.run_turn(
			target_role=target_role,
			target_company=target_company,
			difficulty=difficulty,
			interview_type=interview_type,
			history=[],
			user_audio_path='',
			ai_audio_relpath=ai_rel,
			is_first_turn=True,
			include_resume=session.include_resume,
			resume_context=session.resume_context,
			candidate_name=candidate_name,
		)
	except PipelineUnavailableError as exc:
		session.status = InterviewSession.STATUS_ABORTED
		session.save(update_fields=['status', 'updated_at'])
		return JsonResponse({'ok': False, 'error': str(exc)}, status=503)
	except Exception as exc:
		session.status = InterviewSession.STATUS_ABORTED
		session.save(update_fields=['status', 'updated_at'])
		return JsonResponse({'ok': False, 'error': f'Failed to start interview: {exc}'}, status=500)

	turn = InterviewTurn.objects.create(
		session=session,
		turn_index=1,
		user_transcript='',
		ai_response=result.ai_question,
		ai_feedback=result.ai_feedback,
		ai_audio_path=result.ai_audio_relpath,
		processing_ms=result.processing_ms,
	)

	return JsonResponse(
		{
			'ok': True,
			'session_id': session.id,
			'turn_id': turn.id,
			'turn_index': turn.turn_index,
			'ai_question': turn.ai_response,
			'ai_feedback': turn.ai_feedback,
			'should_offer_coding_ide': _should_offer_coding_ide(turn.ai_response, session.interview_type),
			'ai_audio_url': _build_media_url(request, turn.ai_audio_path),
			'ai_lipsync_url': _build_media_url(request, result.ai_lipsync_relpath) if result.ai_lipsync_relpath else '',
			'timings': result.timings,
			'debug_retrieval': result.rag_context,
		}
	)


@login_required
@require_POST
def live_interview_turn_api(request):
	session_id = request.POST.get('session_id')
	if not session_id:
		return JsonResponse({'ok': False, 'error': 'session_id is required'}, status=400)

	try:
		session = InterviewSession.objects.get(id=session_id, user=request.user)
	except InterviewSession.DoesNotExist:
		return JsonResponse({'ok': False, 'error': 'Interview session not found'}, status=404)

	upload = request.FILES.get('audio')
	user_text = str(request.POST.get('user_text', '') or '').strip()
	if upload is None and not user_text:
		return JsonResponse({'ok': False, 'error': 'audio file or user_text is required'}, status=400)

	next_turn_index = (session.turns.order_by('-turn_index').values_list('turn_index', flat=True).first() or 0) + 1
	user_rel, ai_rel = _build_audio_paths(session, next_turn_index)
	user_audio_abs = Path(settings.MEDIA_ROOT) / user_rel
	if upload is not None:
		user_audio_abs.parent.mkdir(parents=True, exist_ok=True)
		with user_audio_abs.open('wb+') as destination:
			for chunk in upload.chunks():
				destination.write(chunk)
	else:
		user_rel = ''

	history = _session_history(session)
	pipeline = InterviewPipeline.instance()
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	candidate_name = _resolve_candidate_name(
		user=request.user,
		include_resume=session.include_resume,
		resume_text=session.resume_context or profile.resume_text,
	)
	followup_state = _CODING_FOLLOWUP_STATE.get(str(session.id))
	if isinstance(followup_state, dict) and followup_state.get('active'):
		questions = followup_state.get('questions') or []
		next_index = int(followup_state.get('next_index', 0) or 0)
		if next_index < len(questions):
			if user_text:
				user_transcript = user_text
			else:
				try:
					stt_result = pipeline.transcribe(str(user_audio_abs))
				except Exception:
					stt_result = {'transcript': '', 'confidence': 0.0}
				user_transcript = str(stt_result.get('transcript', '') or '').strip()

			ai_question = str(questions[next_index]).strip()
			ai_feedback = 'Code follow-up mode: focus on algorithm, complexity, and correctness from your implementation.'

			try:
				ai_audio_abs = Path(settings.MEDIA_ROOT) / ai_rel
				tts_artifacts = pipeline.synthesize(ai_question, ai_audio_abs)
				ai_lipsync_rel = str(tts_artifacts.get('ai_lipsync_relpath', '') or '')
			except Exception:
				ai_lipsync_rel = ''

			turn = InterviewTurn.objects.create(
				session=session,
				turn_index=next_turn_index,
				user_transcript=user_transcript,
				ai_response=ai_question,
				ai_feedback=ai_feedback,
				user_audio_path=user_rel,
				ai_audio_path=ai_rel,
				processing_ms=0,
			)

			followup_state['next_index'] = next_index + 1
			if followup_state['next_index'] >= len(questions):
				followup_state['active'] = False

			return JsonResponse(
				{
					'ok': True,
					'session_id': session.id,
					'turn_id': turn.id,
					'turn_index': turn.turn_index,
					'user_transcript': turn.user_transcript,
					'ai_question': turn.ai_response,
					'ai_feedback': turn.ai_feedback,
					'should_offer_coding_ide': True,
					'ai_audio_url': _build_media_url(request, turn.ai_audio_path),
					'ai_lipsync_url': _build_media_url(request, ai_lipsync_rel) if ai_lipsync_rel else '',
					'timings': {'whisper_ms': 0, 'llm_ms': 0, 'tts_ms': 0, 'total_ms': 0},
					'debug_retrieval': [
						{
							'question': 'Code-aware follow-up mode',
							'rationale': str(followup_state.get('source_summary', '')),
							'company': session.target_company,
							'role': session.target_role,
							'difficulty': session.difficulty,
							'interview_type': session.interview_type,
							'score': 'custom',
						}
					],
				}
			)

	try:
		result = pipeline.run_turn(
			target_role=session.target_role,
			target_company=session.target_company,
			difficulty=session.difficulty,
			interview_type=session.interview_type,
			history=history,
			user_audio_path=str(user_audio_abs) if upload is not None else '',
			ai_audio_relpath=ai_rel,
			is_first_turn=False,
			user_transcript_override=user_text,
			include_resume=session.include_resume,
			resume_context=session.resume_context,
			candidate_name=candidate_name,
		)
	except PipelineUnavailableError as exc:
		return JsonResponse({'ok': False, 'error': str(exc)}, status=503)
	except Exception as exc:
		return JsonResponse({'ok': False, 'error': f'Failed to process turn: {exc}'}, status=500)

	turn = InterviewTurn.objects.create(
		session=session,
		turn_index=next_turn_index,
		user_transcript=result.user_transcript,
		ai_response=result.ai_question,
		ai_feedback=result.ai_feedback,
		user_audio_path=user_rel,
		ai_audio_path=result.ai_audio_relpath,
		processing_ms=result.processing_ms,
	)

	return JsonResponse(
		{
			'ok': True,
			'session_id': session.id,
			'turn_id': turn.id,
			'turn_index': turn.turn_index,
			'user_transcript': turn.user_transcript,
			'ai_question': turn.ai_response,
			'ai_feedback': turn.ai_feedback,
			'should_offer_coding_ide': _should_offer_coding_ide(turn.ai_response, session.interview_type),
			'ai_audio_url': _build_media_url(request, turn.ai_audio_path),
			'ai_lipsync_url': _build_media_url(request, result.ai_lipsync_relpath) if result.ai_lipsync_relpath else '',
			'timings': result.timings,
			'debug_retrieval': result.rag_context,
		}
	)


@login_required
def live_interview_coding_question_api(request):
	session_id = request.GET.get('session_id')
	if not session_id:
		return JsonResponse({'ok': False, 'error': 'session_id is required'}, status=400)

	try:
		session = InterviewSession.objects.get(id=session_id, user=request.user)
	except InterviewSession.DoesNotExist:
		return JsonResponse({'ok': False, 'error': 'Interview session not found'}, status=404)

	try:
		pack = _get_or_create_coding_pack(session)
	except Exception as exc:
		return JsonResponse({'ok': False, 'error': f'Could not prepare coding question: {exc}'}, status=500)

	return JsonResponse(
		{
			'ok': True,
			'session_id': session.id,
			'title': pack['title'],
			'company': pack['company'],
			'difficulty': pack['difficulty'],
			'topics': pack['topics'],
			'link': pack['link'],
			'selection_reason': pack['selection_reason'],
			'prompt': pack['prompt'],
			'constraints': pack['constraints'],
			'function_name': pack['function_name'],
			'starter_code': pack['starter_code'],
			'visible_tests': pack['visible_tests'],
		}
	)


@login_required
@require_POST
def live_interview_coding_evaluate_api(request):
	try:
		payload = json.loads(request.body.decode('utf-8') or '{}')
	except json.JSONDecodeError:
		return JsonResponse({'ok': False, 'error': 'Invalid JSON payload'}, status=400)

	session_id = str(payload.get('session_id') or '').strip()
	action = str(payload.get('action') or 'run').strip().lower()
	source_code = str(payload.get('source_code') or '')

	if not session_id:
		return JsonResponse({'ok': False, 'error': 'session_id is required'}, status=400)
	if not source_code.strip():
		return JsonResponse({'ok': False, 'error': 'source_code is required'}, status=400)

	try:
		session = InterviewSession.objects.get(id=session_id, user=request.user)
	except InterviewSession.DoesNotExist:
		return JsonResponse({'ok': False, 'error': 'Interview session not found'}, status=404)

	try:
		pack = _get_or_create_coding_pack(session)
	except Exception as exc:
		return JsonResponse({'ok': False, 'error': f'Question pack unavailable: {exc}'}, status=500)

	if action == 'run_output':
		run_result = _run_python_output(source_code)
		if 'error' in run_result:
			return JsonResponse({'ok': False, 'error': run_result['error']}, status=400)
		return JsonResponse(
			{
				'ok': True,
				'action': action,
				'run_ok': bool(run_result.get('ok')),
				'returncode': int(run_result.get('returncode', 1)),
				'stdout': str(run_result.get('stdout', '') or ''),
				'stderr': str(run_result.get('stderr', '') or ''),
			}
		)

	visible_tests = pack.get('visible_tests', [])
	hidden_tests = pack.get('hidden_tests', [])
	test_set = visible_tests if action == 'run' else (visible_tests + hidden_tests)

	result = _run_python_evaluator(source_code, str(pack.get('function_name', 'solve')), test_set)
	if not result.get('ok'):
		return JsonResponse({'ok': False, 'error': result.get('error', 'Evaluation failed')}, status=400)

	results = result.get('results', [])
	failed = [item for item in results if not item.get('passed')]

	return JsonResponse(
		{
			'ok': True,
			'action': action,
			'passed_count': result.get('passed_count', 0),
			'total_count': result.get('total_count', 0),
			'failed_tests': failed[:4],
			'all_passed': int(result.get('passed_count', 0)) == int(result.get('total_count', 0)),
			'followup_mode': _activate_code_followup_mode(
				session=session,
				pack=pack,
				source_code=source_code,
				all_passed=int(result.get('passed_count', 0)) == int(result.get('total_count', 0)),
				failed_tests=failed[:4],
			) if action == 'submit' else {'enabled': False, 'first_question': '', 'remaining_count': 0},
		}
	)


@login_required
def replay_page(request):
	context = _build_replay_context(request, request.user, request.GET.get('session'))
	return render(request, 'Replay-Page-4014a9e4ef52443eb457663a353786b0.html', context)


@login_required
def feedback_dashboard(request):
	context = _build_feedback_context(request.user, request.GET.get('session'))
	return render(request, 'Feedback-Dashboard-e357383ccf44499a9e9039de4a019dab.html', context)


@login_required
def settings_page(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	upload_message = ''
	upload_error = ''
	has_resume_file = bool(profile.resume_file)

	# Auto-retry extraction on previously uploaded files that have empty cached text.
	if has_resume_file and not (profile.resume_text or '').strip():
		recovered = _refresh_resume_text_from_saved_file(profile)
		if recovered:
			upload_message = 'Resume text extracted successfully from your existing uploaded file.'

	if request.method == 'POST':
		action = str(request.POST.get('resume_action') or 'upload').strip().lower()
		if action == 'delete':
			if profile.resume_file:
				profile.resume_file.delete(save=False)
			profile.resume_file = None
			profile.resume_text = ''
			profile.save(update_fields=['resume_file', 'resume_text', 'updated_at'])
			has_resume_file = False
			upload_message = 'Resume deleted. You can upload a new resume now.'
		else:
			if has_resume_file:
				if not (profile.resume_text or '').strip():
					recovered = _refresh_resume_text_from_saved_file(profile)
					if recovered:
						upload_message = 'Resume already uploaded. Text extraction has now been recovered successfully.'
					else:
						upload_error = 'Resume already uploaded and extraction is still empty. Delete it once and re-upload after this update.'
				else:
					upload_error = 'Resume already uploaded. Delete existing resume before uploading a new one.'
			else:
				resume_file = request.FILES.get('resume_file')
				if not resume_file:
					upload_error = 'Please choose a resume file to upload.'
				else:
					allowed = {'.pdf', '.docx', '.txt', '.md'}
					ext = os.path.splitext(str(resume_file.name or '').lower())[1]
					if ext not in allowed:
						upload_error = 'Unsupported file type. Upload PDF, DOCX, TXT, or MD.'
					else:
						resume_text = _extract_resume_text(resume_file)
						profile.resume_file = resume_file
						profile.resume_text = resume_text
						profile.save(update_fields=['resume_file', 'resume_text', 'updated_at'])
						has_resume_file = True
						if resume_text.strip():
							upload_message = 'Resume uploaded successfully. Final round can now include resume-based questions.'
						else:
							upload_error = 'Resume uploaded, but text extraction failed. Delete it and upload a text-readable PDF/DOCX/TXT.'

	context = _build_user_metrics_context(request.user)
	context['resume_uploaded'] = bool((profile.resume_text or '').strip())
	context['resume_file_uploaded'] = has_resume_file
	context['resume_file_name'] = os.path.basename(profile.resume_file.name) if profile.resume_file else ''
	context['resume_upload_message'] = upload_message
	context['resume_upload_error'] = upload_error
	return render(request, 'Settings-f0098eb3e15f4b279780bd050d42ab32.html', context)


@login_required
def profile_page(request):
	context = _build_user_metrics_context(request.user)
	return render(request, 'profile.html', context)


@login_required
def results_page(request):
	return redirect('history_page')


def privacy_policy(request):
	return render(request, 'privacy-policy.html')


def terms_of_service(request):
	return render(request, 'terms-of-service.html')


def contact_page(request):
	return render(request, 'contact.html')
