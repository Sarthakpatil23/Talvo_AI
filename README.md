# Talvo_AI

## Google Authentication Setup

This project now uses `django-allauth` for Google sign-in and first-time registration onboarding.

### 1. Set environment variables

Use the values from `.env.example`:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`

On Windows PowerShell:

```powershell
$env:GOOGLE_OAUTH_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
$env:GOOGLE_OAUTH_CLIENT_SECRET="your-google-client-secret"
```

### 2. Google Cloud Console OAuth redirect URI

Configure this redirect URI in your Google OAuth app:

`http://127.0.0.1:8000/accounts/google/login/callback/`

If you use `localhost`, also add:

`http://localhost:8000/accounts/google/login/callback/`

### 3. Run the app

```powershell
c:/TALVO/.venv/Scripts/python.exe manage.py runserver
```

### 4. Auth flow

1. Go to `/auth/login/` and sign in with Google.
2. First-time users are redirected to `/auth/registration/`.
3. Onboarding requires:
	- Target Role
	- Experience Level
	- Target Company
4. Optional onboarding fields:
	- Interview Focus
	- Confidence Level