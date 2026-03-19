from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class UserProfile(models.Model):
	EXPERIENCE_CHOICES = [
		('entry', 'Entry Level'),
		('mid', 'Mid Level'),
		('senior', 'Senior Level'),
		('lead', 'Lead / Manager'),
	]

	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
	target_role = models.CharField(max_length=140)
	experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES)
	target_company = models.CharField(max_length=140)
	interview_focus = models.CharField(max_length=180, blank=True)
	confidence_level = models.PositiveSmallIntegerField(
		null=True,
		blank=True,
		validators=[MinValueValidator(1), MaxValueValidator(10)],
	)
	profile_completed = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.user.email or self.user.username} profile"


class InterviewSession(models.Model):
	STATUS_ACTIVE = 'active'
	STATUS_COMPLETED = 'completed'
	STATUS_ABORTED = 'aborted'
	STATUS_CHOICES = [
		(STATUS_ACTIVE, 'Active'),
		(STATUS_COMPLETED, 'Completed'),
		(STATUS_ABORTED, 'Aborted'),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interview_sessions')
	target_role = models.CharField(max_length=140)
	target_company = models.CharField(max_length=140)
	difficulty = models.CharField(max_length=20, default='Medium')
	interview_type = models.CharField(max_length=40, default='Behavioral')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
	started_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.user_id} - {self.target_company} {self.target_role} ({self.status})"


class InterviewTurn(models.Model):
	session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='turns')
	turn_index = models.PositiveIntegerField()
	user_transcript = models.TextField(blank=True)
	ai_response = models.TextField()
	ai_feedback = models.TextField(blank=True)
	user_audio_path = models.CharField(max_length=255, blank=True)
	ai_audio_path = models.CharField(max_length=255, blank=True)
	processing_ms = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['turn_index', 'id']
		unique_together = [('session', 'turn_index')]

	def __str__(self):
		return f"session={self.session_id} turn={self.turn_index}"
