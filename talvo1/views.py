from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegistrationOnboardingForm
from .models import UserProfile


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
	return render(request, 'Live-Interview-36d6010513664b89ae2c813c331e830e.html')


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
