from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import cv2
import mediapipe as mp
import numpy as np


LEFT_EYE_OUTER = 33
LEFT_EYE_INNER = 133
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145

RIGHT_EYE_OUTER = 263
RIGHT_EYE_INNER = 362
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374

NOSE_TIP = 1
LEFT_IRIS_IDX = [468, 469, 470, 471, 472]
RIGHT_IRIS_IDX = [473, 474, 475, 476, 477]


@dataclass
class SessionStats:
    total_frames: int = 0
    frames_with_eye_contact: int = 0
    frames_with_face_detected: int = 0


@dataclass
class RuntimeState:
    away_started_at: Optional[float] = None
    low_attention: bool = False
    emotion_label: str = "neutral"


def _landmark_to_pixel(landmark, width: int, height: int) -> tuple[int, int]:
    x = int(landmark.x * width)
    y = int(landmark.y * height)
    return x, y


def _normalized_ratio(value: float, low: float, high: float, default: float = 0.5) -> float:
    span = high - low
    if abs(span) < 1e-6:
        return default
    return float((value - low) / span)


def _map_emotion(raw_label: str) -> str:
    label = str(raw_label or "").strip().lower()
    if label in {"neutral", "calm"}:
        return "neutral"
    if label in {"happy", "joy"}:
        return "happy"
    if label in {"surprise", "surprised", "uncertain"}:
        return "confused"
    if label in {"fear", "angry", "sad", "disgust"}:
        return "nervous"
    return "neutral"


def detect_face(frame: np.ndarray, face_mesh: Any) -> Optional[dict[str, Any]]:
    """Detect one face and return landmarks/bounding box data."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    if not results.multi_face_landmarks:
        return None

    face_landmarks = results.multi_face_landmarks[0]
    height, width = frame.shape[:2]

    points = np.array(
        [_landmark_to_pixel(lm, width, height) for lm in face_landmarks.landmark],
        dtype=np.int32,
    )

    x_min = int(np.clip(points[:, 0].min(), 0, width - 1))
    y_min = int(np.clip(points[:, 1].min(), 0, height - 1))
    x_max = int(np.clip(points[:, 0].max(), 0, width - 1))
    y_max = int(np.clip(points[:, 1].max(), 0, height - 1))

    return {
        "landmarks": points,
        "bbox": (x_min, y_min, x_max, y_max),
    }


def detect_gaze(face_data: dict[str, Any]) -> tuple[str, dict[str, float]]:
    """Estimate gaze direction using eye/iris geometry and head orientation."""
    landmarks: np.ndarray = face_data["landmarks"]

    left_outer = landmarks[LEFT_EYE_OUTER]
    left_inner = landmarks[LEFT_EYE_INNER]
    left_top = landmarks[LEFT_EYE_TOP]
    left_bottom = landmarks[LEFT_EYE_BOTTOM]

    right_outer = landmarks[RIGHT_EYE_OUTER]
    right_inner = landmarks[RIGHT_EYE_INNER]
    right_top = landmarks[RIGHT_EYE_TOP]
    right_bottom = landmarks[RIGHT_EYE_BOTTOM]

    nose = landmarks[NOSE_TIP]

    has_iris = landmarks.shape[0] > RIGHT_IRIS_IDX[-1]
    if has_iris:
        left_iris = landmarks[LEFT_IRIS_IDX].mean(axis=0)
        right_iris = landmarks[RIGHT_IRIS_IDX].mean(axis=0)
    else:
        left_iris = (left_outer + left_inner) / 2.0
        right_iris = (right_outer + right_inner) / 2.0

    left_low_x, left_high_x = sorted([float(left_outer[0]), float(left_inner[0])])
    right_low_x, right_high_x = sorted([float(right_outer[0]), float(right_inner[0])])
    left_low_y, left_high_y = sorted([float(left_top[1]), float(left_bottom[1])])
    right_low_y, right_high_y = sorted([float(right_top[1]), float(right_bottom[1])])

    left_h = _normalized_ratio(float(left_iris[0]), left_low_x, left_high_x)
    right_h = _normalized_ratio(float(right_iris[0]), right_low_x, right_high_x)
    h_ratio = float((left_h + right_h) / 2.0)

    left_v = _normalized_ratio(float(left_iris[1]), left_low_y, left_high_y)
    right_v = _normalized_ratio(float(right_iris[1]), right_low_y, right_high_y)
    v_ratio = float((left_v + right_v) / 2.0)

    eye_mid = (left_outer + right_outer) / 2.0
    eye_distance = float(np.linalg.norm(right_outer - left_outer)) + 1e-6
    yaw = float((nose[0] - eye_mid[0]) / eye_distance)
    pitch = float((nose[1] - eye_mid[1]) / eye_distance)

    if pitch > 0.19 or v_ratio > 0.68:
        gaze = "down"
    elif yaw < -0.17 or h_ratio < 0.36:
        gaze = "left"
    elif yaw > 0.17 or h_ratio > 0.64:
        gaze = "right"
    else:
        gaze = "center"

    details = {
        "h_ratio": h_ratio,
        "v_ratio": v_ratio,
        "yaw": yaw,
        "pitch": pitch,
    }
    return gaze, details


def calculate_scores(stats: SessionStats) -> dict[str, float]:
    """Compute confidence metrics for eye contact and attention."""
    total = max(stats.total_frames, 1)
    face_frames = max(stats.frames_with_face_detected, 1)

    eye_contact_score = (stats.frames_with_eye_contact / face_frames) * 100.0
    attention_score = (stats.frames_with_face_detected / total) * 100.0

    return {
        "eye_contact_score": round(eye_contact_score, 2),
        "attention_score": round(attention_score, 2),
    }


def _load_emotion_backend() -> tuple[Optional[str], Optional[Any]]:
    """Try FER first, then DeepFace; both remain optional."""
    try:
        from fer import FER

        return "fer", FER(mtcnn=False)
    except Exception:
        pass

    try:
        from deepface import DeepFace

        return "deepface", DeepFace
    except Exception:
        return None, None


def _detect_emotion(frame: np.ndarray, face_bbox: tuple[int, int, int, int], backend_name: Optional[str], backend_obj: Any) -> Optional[str]:
    if not backend_name or backend_obj is None:
        return None

    x1, y1, x2, y2 = face_bbox
    if x2 <= x1 or y2 <= y1:
        return None

    face_roi = frame[y1:y2, x1:x2]
    if face_roi.size == 0:
        return None

    try:
        if backend_name == "fer":
            rgb_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
            detected = backend_obj.detect_emotions(rgb_roi)
            if not detected:
                return None
            emotions = detected[0].get("emotions", {})
            if not emotions:
                return None
            dominant = max(emotions, key=emotions.get)
            return _map_emotion(dominant)

        if backend_name == "deepface":
            result = backend_obj.analyze(
                img_path=face_roi,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="opencv",
                silent=True,
            )
            if isinstance(result, list):
                result = result[0] if result else {}
            dominant = str(result.get("dominant_emotion", "")).strip().lower()
            return _map_emotion(dominant)
    except Exception:
        return None

    return None


def _draw_overlay(
    frame: np.ndarray,
    face_data: Optional[dict[str, Any]],
    gaze_direction: str,
    attention_status: str,
    scores: dict[str, float],
    emotion_label: str,
) -> None:
    if face_data:
        x1, y1, x2, y2 = face_data["bbox"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (52, 211, 153), 2)

        for idx in [LEFT_EYE_OUTER, LEFT_EYE_INNER, RIGHT_EYE_OUTER, RIGHT_EYE_INNER, NOSE_TIP]:
            pt = tuple(face_data["landmarks"][idx])
            cv2.circle(frame, pt, 2, (255, 255, 0), -1)

    eye_text = "Eye Contact: Good" if gaze_direction == "center" else f"Eye Contact: Poor ({gaze_direction})"
    cv2.putText(frame, eye_text, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2, cv2.LINE_AA)

    attention_text = f"Attention: {attention_status}"
    cv2.putText(frame, attention_text, (18, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2, cv2.LINE_AA)

    score_text = f"Eye Score: {scores['eye_contact_score']:.1f}%  |  Attention Score: {scores['attention_score']:.1f}%"
    cv2.putText(frame, score_text, (18, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (40, 40, 40), 2, cv2.LINE_AA)

    emotion_text = f"Emotion: {emotion_label}"
    cv2.putText(frame, emotion_text, (18, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (40, 40, 40), 2, cv2.LINE_AA)


def _feedback_from_scores(scores: dict[str, float]) -> str:
    eye = scores["eye_contact_score"]
    attention = scores["attention_score"]

    if attention < 75:
        return "Stay within camera frame consistently to improve attention score."
    if eye < 60:
        return "Maintain better eye contact by looking near the webcam while speaking."
    if eye < 75:
        return "Good progress. Keep your gaze centered more consistently for stronger presence."
    return "Strong interview presence. Keep this eye contact and attention pattern."


def run_realtime_interview_behavior_session(
    camera_index: int = 0,
    away_threshold_seconds: float = 2.0,
    enable_emotion: bool = True,
) -> dict[str, Any]:
    """Run real-time interview behavior tracking from webcam.

    Press 'q' to end the session.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Unable to open webcam. Check camera access or camera index.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.55,
        min_tracking_confidence=0.55,
    )

    emotion_backend_name, emotion_backend = _load_emotion_backend() if enable_emotion else (None, None)

    stats = SessionStats()
    state = RuntimeState()
    frame_id = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            now = time.time()

            stats.total_frames += 1
            frame_id += 1

            face_data = detect_face(frame, face_mesh)
            if face_data is None:
                gaze_direction = "away"
                attention_status = "Not attentive"
                state.away_started_at = None
                state.low_attention = False
            else:
                stats.frames_with_face_detected += 1
                gaze_direction, _ = detect_gaze(face_data)

                if gaze_direction == "center":
                    stats.frames_with_eye_contact += 1
                    state.away_started_at = None
                    state.low_attention = False
                else:
                    if state.away_started_at is None:
                        state.away_started_at = now
                    state.low_attention = (now - state.away_started_at) >= away_threshold_seconds

                attention_status = "Low attention" if state.low_attention else "Active"

                if emotion_backend_name and (frame_id % 12 == 0):
                    emotion = _detect_emotion(frame, face_data["bbox"], emotion_backend_name, emotion_backend)
                    if emotion:
                        state.emotion_label = emotion

            scores = calculate_scores(stats)
            _draw_overlay(
                frame=frame,
                face_data=face_data,
                gaze_direction=gaze_direction,
                attention_status=attention_status,
                scores=scores,
                emotion_label=state.emotion_label,
            )

            cv2.imshow("Talvo Interview Behavior Monitor", frame)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        cap.release()
        face_mesh.close()
        cv2.destroyAllWindows()

    summary_scores = calculate_scores(stats)
    feedback = _feedback_from_scores(summary_scores)

    summary = {
        "total_frames_processed": stats.total_frames,
        "frames_with_eye_contact": stats.frames_with_eye_contact,
        "frames_with_face_detected": stats.frames_with_face_detected,
        "eye_contact_score": summary_scores["eye_contact_score"],
        "attention_score": summary_scores["attention_score"],
        "feedback": feedback,
    }

    print("\n=== Interview Behavior Summary ===")
    print(f"Total frames processed: {summary['total_frames_processed']}")
    print(f"Frames with eye contact: {summary['frames_with_eye_contact']}")
    print(f"Frames with face detected: {summary['frames_with_face_detected']}")
    print(f"Eye Contact Score: {summary['eye_contact_score']}%")
    print(f"Attention Score: {summary['attention_score']}%")
    print(f"Feedback: {summary['feedback']}")

    return summary


if __name__ == "__main__":
    run_realtime_interview_behavior_session()
