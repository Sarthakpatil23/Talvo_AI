# Standalone Posture + Eye Contact Prototype

This prototype is intentionally **not wired** to the Talvo project frontend or backend.

## What it does

- Opens webcam locally in the browser.
- Runs MediaPipe Face and Pose landmark inference.
- Computes heuristic `eyeContactScore` and `postureScore`.
- Displays live scores and status chips.
- Lets you export captured metric samples as JSON.

## How to run

1. From `Talvo_AI`, start a simple static server:

```powershell
python -m http.server 8088
```

2. Open this URL:

`http://127.0.0.1:8088/prototypes/posture-eye-contact-standalone/index.html`

3. Click **Start Camera**.

## Notes

- This uses pretrained models from CDN (no custom dataset/training required).
- It is coaching-oriented, not a proctoring-grade detector.
- For best results: face camera directly, use decent lighting, keep webcam near eye level.
