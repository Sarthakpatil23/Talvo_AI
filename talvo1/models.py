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
