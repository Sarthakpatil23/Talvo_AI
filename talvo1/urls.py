from django.urls import path

from . import views


urlpatterns = [
    path('', views.landing, name='landing'),
    path('auth/login/', views.auth_login, name='auth_login'),
    path('auth/post-login/', views.post_login_redirect, name='post_login_redirect'),
    path('auth/registration/', views.registration_onboarding, name='registration_onboarding'),
    path('auth/logout/', views.logout_user, name='logout_user'),
    path('talvo-ai-interview-prep/', views.talvo_ai_interview_prep, name='talvo_ai_interview_prep'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('history/', views.history_page, name='history_page'),
    path('interview-setup/', views.interview_setup, name='interview_setup'),
    path('live-interview/', views.live_interview, name='live_interview'),
    path('api/live-interview/start/', views.live_interview_start_api, name='live_interview_start_api'),
    path('api/live-interview/turn/', views.live_interview_turn_api, name='live_interview_turn_api'),
    path('replay/', views.replay_page, name='replay_page'),
    path('feedback-dashboard/', views.feedback_dashboard, name='feedback_dashboard'),
    path('settings/', views.settings_page, name='settings_page'),
    path('profile/', views.profile_page, name='profile_page'),
    path('results/', views.results_page, name='results_page'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('contact/', views.contact_page, name='contact_page'),
]