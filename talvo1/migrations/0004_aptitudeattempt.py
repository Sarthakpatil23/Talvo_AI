from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('talvo1', '0003_profile_resume_and_session_resume_context'),
    ]

    operations = [
        migrations.CreateModel(
            name='AptitudeAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company', models.CharField(max_length=140)),
                ('score', models.PositiveSmallIntegerField(default=0)),
                ('total_questions', models.PositiveSmallIntegerField(default=0)),
                ('duration_seconds', models.PositiveIntegerField(default=0)),
                ('responses', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='aptitude_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
