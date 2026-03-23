import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RegistrationOnboardingForm
from .interview_pipeline import InterviewPipeline, PipelineUnavailableError
from .models import InterviewSession, InterviewTurn, UserProfile


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
def history_page(request):
	context = _build_results_context(request.user)
	return render(request, 'History-Page-a3d819cc716944daa8cb80c50d943ada.html', context)


@login_required
def interview_setup(request):
	return render(request, 'Interview-Setup-82549d84a8874a5d8a6eac01c3e830e0.html')


@login_required
def live_interview(request):
	prefill_role, prefill_type = _enforce_software_focus(
		request.GET.get('role', ''),
		request.GET.get('type', ''),
	)
	context = {
		'prefill_role': prefill_role,
		'prefill_company': request.GET.get('company', ''),
		'prefill_difficulty': request.GET.get('difficulty', 'Medium'),
		'prefill_type': prefill_type,
		'prefill_mode': request.GET.get('mode', 'avatar'),
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


def _enforce_software_focus(role: str, interview_type: str):
	enabled = str(getattr(settings, 'INTERVIEW_SOFTWARE_ONLY', '1')).strip().lower() in {'1', 'true', 'yes', 'on'}
	if not enabled:
		return (role or '').strip() or 'Software Engineer', (interview_type or '').strip() or 'Technical'

	allowed_raw = str(getattr(settings, 'INTERVIEW_SOFTWARE_ALLOWED_TYPES', 'technical,coding,system design,debugging,behavioral'))
	allowed = [x.strip().lower() for x in allowed_raw.split(',') if x.strip()]
	pretty = {
		'technical': 'Technical',
		'coding': 'Coding',
		'system design': 'System Design',
		'debugging': 'Debugging',
		'behavioral': 'Behavioral',
	}

	requested = (interview_type or '').strip().lower()
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
	interview_type = (payload.get('interview_type') or '').strip() or 'Technical'
	target_role, interview_type = _enforce_software_focus(target_role, interview_type)

	session = InterviewSession.objects.create(
		user=request.user,
		target_role=target_role,
		target_company=target_company,
		difficulty=difficulty,
		interview_type=interview_type,
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
	if upload is None:
		return JsonResponse({'ok': False, 'error': 'audio file is required'}, status=400)

	next_turn_index = (session.turns.order_by('-turn_index').values_list('turn_index', flat=True).first() or 0) + 1
	user_rel, ai_rel = _build_audio_paths(session, next_turn_index)
	user_audio_abs = Path(settings.MEDIA_ROOT) / user_rel
	user_audio_abs.parent.mkdir(parents=True, exist_ok=True)
	with user_audio_abs.open('wb+') as destination:
		for chunk in upload.chunks():
			destination.write(chunk)

	history = _session_history(session)
	pipeline = InterviewPipeline.instance()

	try:
		result = pipeline.run_turn(
			target_role=session.target_role,
			target_company=session.target_company,
			difficulty=session.difficulty,
			interview_type=session.interview_type,
			history=history,
			user_audio_path=str(user_audio_abs),
			ai_audio_relpath=ai_rel,
			is_first_turn=False,
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
			'ai_audio_url': _build_media_url(request, turn.ai_audio_path),
			'ai_lipsync_url': _build_media_url(request, result.ai_lipsync_relpath) if result.ai_lipsync_relpath else '',
			'timings': result.timings,
			'debug_retrieval': result.rag_context,
		}
	)


@login_required
def replay_page(request):
	return render(request, 'Replay-Page-4014a9e4ef52443eb457663a353786b0.html')


@login_required
def feedback_dashboard(request):
	return render(request, 'Feedback-Dashboard-e357383ccf44499a9e9039de4a019dab.html')


@login_required
def settings_page(request):
	context = _build_user_metrics_context(request.user)
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
