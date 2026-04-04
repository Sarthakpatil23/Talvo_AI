from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image


BASE_KEYS = [
    "rest",
    "openSlight",
    "openMedium",
    "openWide",
    "oSmall",
    "oWide",
    "teethE",
    "fv",
    "lth",
    "mbp",
    "idleSmile",
    "jawDrop",
]

TRANSITION_SPECS = {
    "bridgeClosedToSlight": ("rest", "openSlight"),
    "bridgeSlightToMedium": ("openSlight", "openMedium"),
    "bridgeMediumToWide": ("openMedium", "openWide"),
    "bridgeOToE": ("oSmall", "teethE"),
    "bridgeEToClosed": ("teethE", "rest"),
    "bridgeFvToClosed": ("fv", "rest"),
}

TARGETS = {
    "rest": {"open": 0.06, "teeth": 0.02, "aspect": 0.95, "round": 0.12, "red": 0.50},
    "openSlight": {"open": 0.30, "teeth": 0.10, "aspect": 0.70, "round": 0.25, "red": 0.60},
    "openMedium": {"open": 0.52, "teeth": 0.15, "aspect": 0.62, "round": 0.33, "red": 0.58},
    "openWide": {"open": 0.84, "teeth": 0.15, "aspect": 0.50, "round": 0.50, "red": 0.55},
    "oSmall": {"open": 0.42, "teeth": 0.08, "aspect": 0.42, "round": 0.60, "red": 0.58},
    "oWide": {"open": 0.74, "teeth": 0.10, "aspect": 0.36, "round": 0.72, "red": 0.55},
    "teethE": {"open": 0.45, "teeth": 0.80, "aspect": 0.80, "round": 0.22, "red": 0.52},
    "fv": {"open": 0.26, "teeth": 0.68, "aspect": 0.88, "round": 0.16, "red": 0.52},
    "lth": {"open": 0.40, "teeth": 0.18, "aspect": 0.55, "round": 0.42, "red": 0.62},
    "mbp": {"open": 0.10, "teeth": 0.02, "aspect": 0.90, "round": 0.10, "red": 0.66},
    "idleSmile": {"open": 0.20, "teeth": 0.40, "aspect": 0.90, "round": 0.12, "red": 0.64},
    "jawDrop": {"open": 0.92, "teeth": 0.10, "aspect": 0.44, "round": 0.62, "red": 0.52},
}

WEIGHTS = {"open": 2.4, "teeth": 1.8, "aspect": 1.0, "round": 0.9, "red": 0.4}


@dataclass
class FrameInfo:
    path: Path
    open_raw: float
    teeth_raw: float
    aspect_raw: float
    round_raw: float
    red_raw: float
    open: float = 0.0
    teeth: float = 0.0
    aspect: float = 0.0
    round: float = 0.0
    red: float = 0.0


def _scale(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 1.0
    lo = float(min(values))
    hi = float(max(values))
    if hi - lo < 1e-9:
        return lo, lo + 1.0
    return lo, hi


def _norm(v: float, lo: float, hi: float) -> float:
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def _extract_features(path: Path) -> FrameInfo:
    image = Image.open(path).convert("RGB")
    arr = np.asarray(image, dtype=np.float32)
    h, w = arr.shape[:2]

    x1, x2 = int(w * 0.33), int(w * 0.67)
    y1, y2 = int(h * 0.34), int(h * 0.58)
    roi = arr[y1:y2, x1:x2]
    rh, rw = roi.shape[:2]

    mx1, mx2 = int(rw * 0.16), int(rw * 0.84)
    my1, my2 = int(rh * 0.36), int(rh * 0.90)
    mouth = roi[my1:my2, mx1:mx2]

    if mouth.size == 0:
        return FrameInfo(path=path, open_raw=0.0, teeth_raw=0.0, aspect_raw=10.0, round_raw=0.0, red_raw=0.0)

    r = mouth[:, :, 0]
    g = mouth[:, :, 1]
    b = mouth[:, :, 2]

    v = np.max(mouth, axis=2)
    mn = np.min(mouth, axis=2)
    s = np.where(v > 1.0, (v - mn) / (v + 1e-6), 0.0)

    dark_mask = v < 76
    teeth_mask = (v > 178) & (s < 0.24)

    open_raw = float(dark_mask.mean())
    teeth_raw = float(teeth_mask.mean())
    red_raw = float(((r - ((g + b) * 0.5)) / 255.0).mean())

    ys, xs = np.where(dark_mask)
    if xs.size > 10:
        width = float(xs.max() - xs.min() + 1) / float(mouth.shape[1])
        height = float(ys.max() - ys.min() + 1) / float(mouth.shape[0])
    else:
        width = 0.0
        height = 0.0

    aspect_raw = float(width / max(height, 1e-6)) if height > 0 else 10.0
    round_raw = float(height / max(width, 1e-6)) if width > 0 else 0.0

    return FrameInfo(
        path=path,
        open_raw=open_raw,
        teeth_raw=teeth_raw,
        aspect_raw=aspect_raw,
        round_raw=round_raw,
        red_raw=red_raw,
    )


def _distance(frame: FrameInfo, key: str) -> float:
    t = TARGETS[key]
    return (
        WEIGHTS["open"] * (frame.open - t["open"]) ** 2
        + WEIGHTS["teeth"] * (frame.teeth - t["teeth"]) ** 2
        + WEIGHTS["aspect"] * (frame.aspect - t["aspect"]) ** 2
        + WEIGHTS["round"] * (frame.round - t["round"]) ** 2
        + WEIGHTS["red"] * (frame.red - t["red"]) ** 2
    )


def _mean_vector(frames: List[FrameInfo]) -> Dict[str, float]:
    if not frames:
        return {"open": 0.5, "teeth": 0.1, "aspect": 0.7, "round": 0.3, "red": 0.5}
    return {
        "open": float(np.mean([f.open for f in frames])),
        "teeth": float(np.mean([f.teeth for f in frames])),
        "aspect": float(np.mean([f.aspect for f in frames])),
        "round": float(np.mean([f.round for f in frames])),
        "red": float(np.mean([f.red for f in frames])),
    }


def _distance_to_vector(frame: FrameInfo, vec: Dict[str, float]) -> float:
    return (
        WEIGHTS["open"] * (frame.open - vec["open"]) ** 2
        + WEIGHTS["teeth"] * (frame.teeth - vec["teeth"]) ** 2
        + WEIGHTS["aspect"] * (frame.aspect - vec["aspect"]) ** 2
        + WEIGHTS["round"] * (frame.round - vec["round"]) ** 2
        + WEIGHTS["red"] * (frame.red - vec["red"]) ** 2
    )


def build_avatar_assets(src_dir: Path, out_dir: Path) -> dict:
    image_paths = sorted(
        [p for p in src_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}],
        key=lambda p: p.name,
    )
    if not image_paths:
        raise RuntimeError(f"No images found in {src_dir}")

    frames = [_extract_features(p) for p in image_paths]

    open_lo, open_hi = _scale([f.open_raw for f in frames])
    teeth_lo, teeth_hi = _scale([f.teeth_raw for f in frames])
    red_lo, red_hi = _scale([f.red_raw for f in frames])

    for f in frames:
        f.open = _norm(f.open_raw, open_lo, open_hi)
        f.teeth = _norm(f.teeth_raw, teeth_lo, teeth_hi)
        f.red = _norm(f.red_raw, red_lo, red_hi)
        f.aspect = _norm(f.aspect_raw, 0.8, 4.0)
        f.round = _norm(f.round_raw, 0.05, 1.2)

    open_values = np.array([f.open for f in frames], dtype=np.float32)
    teeth_values = np.array([f.teeth for f in frames], dtype=np.float32)
    round_values = np.array([f.round for f in frames], dtype=np.float32)
    aspect_values = np.array([f.aspect for f in frames], dtype=np.float32)
    red_values = np.array([f.red for f in frames], dtype=np.float32)

    q_open = {p: float(np.quantile(open_values, p)) for p in (0.22, 0.25, 0.30, 0.40, 0.45, 0.55, 0.58, 0.62, 0.65, 0.72, 0.75, 0.78, 0.86)}
    q_teeth = {p: float(np.quantile(teeth_values, p)) for p in (0.55, 0.60, 0.72, 0.78)}
    q_round = {p: float(np.quantile(round_values, p)) for p in (0.65, 0.68)}
    q_aspect = {p: float(np.quantile(aspect_values, p)) for p in (0.45,)}
    q_red = {p: float(np.quantile(red_values, p)) for p in (0.55,)}

    def select(mask_fn, fallback_key: str, min_count: int = 24, max_count: int = 120) -> List[FrameInfo]:
        selected = [f for f in frames if mask_fn(f)]
        if len(selected) < min_count:
            existing = {f.path.name for f in selected}
            ranked = sorted(frames, key=lambda f: _distance(f, fallback_key))
            for frame in ranked:
                if frame.path.name in existing:
                    continue
                selected.append(frame)
                existing.add(frame.path.name)
                if len(selected) >= min_count:
                    break
        selected = sorted(selected, key=lambda f: f.path.name)
        if len(selected) > max_count:
            step = len(selected) / float(max_count)
            selected = [selected[int(i * step)] for i in range(max_count)]
        return selected

    buckets: Dict[str, List[FrameInfo]] = {
        'rest': select(lambda f: f.open <= q_open[0.30], 'rest', min_count=36, max_count=130),
        'mbp': select(lambda f: f.open <= q_open[0.22] and f.red >= q_red[0.55], 'mbp', min_count=30, max_count=110),
        'idleSmile': select(lambda f: f.open <= q_open[0.45] and f.teeth >= q_teeth[0.60], 'idleSmile', min_count=24, max_count=90),
        'openSlight': select(lambda f: q_open[0.25] <= f.open <= q_open[0.58], 'openSlight', min_count=36, max_count=120),
        'openMedium': select(lambda f: q_open[0.45] <= f.open <= q_open[0.78], 'openMedium', min_count=36, max_count=120),
        'openWide': select(lambda f: f.open >= q_open[0.72], 'openWide', min_count=30, max_count=110),
        'jawDrop': select(lambda f: f.open >= q_open[0.86] and f.aspect <= q_aspect[0.45], 'jawDrop', min_count=24, max_count=80),
        'oSmall': select(lambda f: q_open[0.40] <= f.open <= q_open[0.65] and f.round >= q_round[0.65], 'oSmall', min_count=28, max_count=90),
        'oWide': select(lambda f: f.open >= q_open[0.62] and f.round >= q_round[0.68], 'oWide', min_count=28, max_count=90),
        'teethE': select(lambda f: f.teeth >= q_teeth[0.78] and q_open[0.25] <= f.open <= q_open[0.75], 'teethE', min_count=26, max_count=95),
        'fv': select(lambda f: f.teeth >= q_teeth[0.72] and f.open <= q_open[0.55], 'fv', min_count=24, max_count=90),
        'lth': select(lambda f: q_open[0.45] <= f.open <= q_open[0.75] and f.teeth <= q_teeth[0.55] and f.red >= q_red[0.55], 'lth', min_count=24, max_count=90),
    }

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_keys: Dict[str, List[str]] = {}

    for key in BASE_KEYS:
        key_dir = out_dir / key
        key_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(buckets[key], key=lambda f: f.path.name)
        rels: List[str] = []
        for idx, frame in enumerate(files):
            dst_name = f"frame_{idx:03d}.jpg"
            dst = key_dir / dst_name
            shutil.copy2(frame.path, dst)
            rels.append(f"talvo1/images/avatar/generated/{key}/{dst_name}")
        manifest_keys[key] = rels

    for bridge_key, (src_key, dst_key) in TRANSITION_SPECS.items():
        vec_src = _mean_vector(buckets.get(src_key, []))
        vec_dst = _mean_vector(buckets.get(dst_key, []))
        bridge_vec = {k: (vec_src[k] + vec_dst[k]) / 2.0 for k in vec_src.keys()}

        ranked = sorted((( _distance_to_vector(f, bridge_vec), f) for f in frames), key=lambda it: it[0])
        chosen = [item[1] for item in ranked[:24]]

        key_dir = out_dir / bridge_key
        key_dir.mkdir(parents=True, exist_ok=True)
        rels: List[str] = []
        for idx, frame in enumerate(chosen):
            dst_name = f"frame_{idx:03d}.jpg"
            dst = key_dir / dst_name
            shutil.copy2(frame.path, dst)
            rels.append(f"talvo1/images/avatar/generated/{bridge_key}/{dst_name}")
        manifest_keys[bridge_key] = rels

    manifest = {
        "version": 1,
        "source_folder": str(src_dir),
        "total_source_images": len(frames),
        "keys": manifest_keys,
    }
    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    summary = {
        "total_source_images": len(frames),
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
        "transition_counts": {k: len(manifest_keys.get(k, [])) for k in TRANSITION_SPECS.keys()},
        "manifest": str(out_dir / "manifest.json"),
    }
    return summary


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root.parent / "Final_images"
    out_dir = repo_root / "talvo1" / "static" / "talvo1" / "images" / "avatar" / "generated"

    summary = build_avatar_assets(src_dir=src_dir, out_dir=out_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
