import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
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
	return render(request, 'History-Page-a3d819cc716944daa8cb80c50d943ada.html')


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
	return render(request, 'Settings-f0098eb3e15f4b279780bd050d42ab32.html')


@login_required
def profile_page(request):
	profile, _ = UserProfile.objects.get_or_create(user=request.user)
	return render(request, 'profile.html', {'profile': profile})


def privacy_policy(request):
	return render(request, 'privacy-policy.html')


def terms_of_service(request):
	return render(request, 'terms-of-service.html')


def contact_page(request):
	return render(request, 'contact.html')
