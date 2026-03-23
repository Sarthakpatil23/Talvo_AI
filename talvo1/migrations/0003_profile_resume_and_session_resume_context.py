from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('talvo1', '0002_interviewsession_interviewturn'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewsession',
            name='include_resume',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='interviewsession',
            name='resume_context',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='resume_file',
            field=models.FileField(blank=True, null=True, upload_to='resumes/'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='resume_text',
            field=models.TextField(blank=True),
        ),
    ]
