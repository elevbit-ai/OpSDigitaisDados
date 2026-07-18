"""
Fingerprint template extraction and matching for OpS Digitais Dados.

Uses OpenCV ORB descriptors on fingerprint images as a portable local
biometric template (works with scanner exports or high-quality photos).

Author: Joaquim Pedro de Morais Filho
"""

from __future__ import annotations

import io
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


@dataclass
class FingerprintTemplate:
    descriptors: np.ndarray  # uint8 Hx32
    keypoints: int
    quality: float
    version: int = 1

    def to_bytes(self) -> bytes:
        payload = {
            "version": self.version,
            "keypoints": self.keypoints,
            "quality": self.quality,
            "descriptors": self.descriptors.astype(np.uint8),
        }
        return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def from_bytes(data: bytes) -> "FingerprintTemplate":
        payload = pickle.loads(data)
        desc = np.asarray(payload["descriptors"], dtype=np.uint8)
        return FingerprintTemplate(
            descriptors=desc,
            keypoints=int(payload.get("keypoints", desc.shape[0] if desc is not None else 0)),
            quality=float(payload.get("quality", 0.0)),
            version=int(payload.get("version", 1)),
        )


def _preprocess(gray: np.ndarray) -> np.ndarray:
    """Enhance ridge contrast for more stable ORB features."""
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    # Normalize size for consistency
    h, w = gray.shape[:2]
    max_side = 512
    scale = max_side / float(max(h, w))
    if scale < 1.0:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    blur = cv2.GaussianBlur(eq, (3, 3), 0)
    return blur


def extract_template(image_path: str | Path) -> FingerprintTemplate:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {path}")

    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Não foi possível ler a imagem da impressão digital.")

    proc = _preprocess(img)
    orb = cv2.ORB_create(nfeatures=1200, scaleFactor=1.2, nlevels=8)
    kps, desc = orb.detectAndCompute(proc, None)
    if desc is None or len(kps) < 20:
        raise ValueError(
            "Qualidade insuficiente da impressão digital. "
            "Use uma imagem mais nítida e bem iluminada (scanner ou foto clara)."
        )

    # Quality heuristic: keypoints + contrast
    contrast = float(proc.std())
    quality = min(100.0, (len(kps) / 12.0) + (contrast / 2.0))
    return FingerprintTemplate(descriptors=desc, keypoints=len(kps), quality=round(quality, 2))


def match_score(probe: FingerprintTemplate, gallery: FingerprintTemplate) -> float:
    """
    Return match percentage 0–100 based on good ORB matches.
    Higher is better.
    """
    if probe.descriptors is None or gallery.descriptors is None:
        return 0.0
    if len(probe.descriptors) < 10 or len(gallery.descriptors) < 10:
        return 0.0

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = bf.knnMatch(probe.descriptors, gallery.descriptors, k=2)
    good = 0
    for m_n in pairs:
        if len(m_n) < 2:
            continue
        m, n = m_n
        if m.distance < 0.75 * n.distance:
            good += 1

    denom = max(min(len(probe.descriptors), len(gallery.descriptors)), 1)
    ratio = good / float(denom)
    # Map ratio to 0–100 (ratio ~0.55+ is a strong match for ORB ridges)
    score = min(100.0, max(0.0, (ratio - 0.05) / 0.55 * 100.0))
    return round(float(score), 2)


def identify(
    probe_path: str | Path,
    gallery: list[tuple[int, int, str, bytes]],
    threshold: float = 35.0,
) -> Optional[dict]:
    """
    1:N identification against gallery templates.
    gallery items: (fp_id, user_id, full_name, template_bytes)
    """
    probe = extract_template(probe_path)
    best = None
    for fp_id, user_id, full_name, blob in gallery:
        try:
            gal = FingerprintTemplate.from_bytes(blob)
        except Exception:
            continue
        score = match_score(probe, gal)
        if best is None or score > best["score"]:
            best = {
                "fp_id": fp_id,
                "user_id": user_id,
                "full_name": full_name,
                "score": score,
                "matched": score >= threshold,
            }
    return best


def save_preview_copy(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = np.fromfile(str(source), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        # raw copy
        dest.write_bytes(source.read_bytes())
        return dest
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        dest.write_bytes(source.read_bytes())
        return dest
    dest.write_bytes(buf.tobytes())
    return dest


def create_demo_fingerprint(path: Path, seed: int = 7) -> Path:
    """Synthetic ridge-like image for offline testing (unique per seed)."""
    rng = np.random.default_rng(seed)
    h, w = 420, 320
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    # Unique orientation / frequency / swirl per seed
    ang = (seed % 17) * 0.19
    fx = 3.2 + (seed % 9) * 0.35
    fy = 14.0 + (seed % 11) * 0.8
    phase = seed * 0.73
    cx, cy = w / 2 + rng.uniform(-20, 20), h / 2 + rng.uniform(-20, 20)
    xr = (xx - cx) * np.cos(ang) + (yy - cy) * np.sin(ang)
    yr = -(xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang)
    ridges = np.sin(xr / fx + phase) + 0.45 * np.sin(yr / fy + phase * 0.5)
    ridges += 0.25 * np.sin((xr * xr + yr * yr) / (900 + seed * 3))
    base = ((ridges - ridges.min()) / (float(np.ptp(ridges)) + 1e-6) * 200).astype(np.uint8)
    noise = rng.integers(0, 55, size=(h, w), dtype=np.uint8)
    img = cv2.add(base, noise)
    # irregular oval mask
    mask = np.zeros((h, w), dtype=np.uint8)
    axes = (100 + seed % 20, 145 + seed % 25)
    cv2.ellipse(mask, (int(cx), int(cy)), axes, ang * 57.3, 0, 360, 255, -1)
    img = cv2.bitwise_and(img, img, mask=mask)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    path.write_bytes(buf.tobytes())
    return path
