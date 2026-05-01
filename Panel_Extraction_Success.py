#!/usr/bin/env python3
"""
Comica Object SVG Miracle

PDF/image/folder -> spatial JSON -> one faithful editable SVG per page.

Core promise:
- Save the rendered page as a page asset.
- Detect panels as movable SVG object groups.
- Save every detected panel as a crop asset.
- Preserve gutters as SVG objects and JSON records.
- Extract PDF-native text line-by-line when available.
- Optionally OCR image/scanned pages with PaddleOCR, line-by-line.
- Store all page geometry in page JSON.
- Rebuild SVGs from JSON, not from temporary memory.

Install base:
    pip install pymupdf pillow opencv-python numpy

Optional OCR:
    pip install paddleocr paddlepaddle

Examples:
    python comica_object_svg_miracle.py input.pdf -o comica_out --pdf-zoom 2 --panel-profile balanced
    python comica_object_svg_miracle.py input.pdf -o comica_out --panel-profile strict
    python comica_object_svg_miracle.py input.pdf -o comica_out --panel-profile loose --panel-source hybrid
    python comica_object_svg_miracle.py image_folder -o comica_out --ocr paddle
    python comica_object_svg_miracle.py input.pdf -o comica_out --ocr paddle --prefer-ocr

Manual rescue panels:
    python comica_object_svg_miracle.py input.pdf -o comica_out --manual-panels panels.json

Manual panels JSON format:
{
  "pages": {
    "1": [[x0, y0, x1, y1], [x0, y0, x1, y1]],
    "2": [{"bbox": [x0, y0, x1, y1], "name": "custom"}]
  }
}
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np
from PIL import Image

SCHEMA_VERSION = "0.5.0"
TOOL_NAME = "comica_object_svg_miracle"
TOOL_VERSION = "0.5.0"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
PDF_EXTS = {".pdf"}


@dataclass
class TextLine:
    id: str
    page: int
    text: str
    bbox: list[float]
    object_type: str = "text_line"
    source: str = "pdf_native"
    block_no: int | None = None
    reading_order: int | None = None
    panel_id: str | None = None
    confidence: float | None = None


@dataclass
class PanelRegion:
    id: str
    page: int
    name: str
    bbox: list[float]
    corners: list[list[float]]
    polygon: list[list[float]]
    reading_order: int
    object_type: str = "comic_panel_region"
    source: str = "contour"
    confidence: float = 0.0
    crop_path: str | None = None
    crop_sha256: str | None = None
    crop_size_bytes: int | None = None


@dataclass
class GutterBand:
    id: str
    page: int
    orientation: str
    bbox: list[float]
    confidence: float
    object_type: str = "gutter_band"


@dataclass
class PanelDetectionConfig:
    profile: str = "balanced"          # strict, balanced, loose, recall, comic
    panel_source: str = "fallback"     # contours, gutters, fallback, hybrid
    max_area_ratio: float = 0.94
    merge_iou: float = 0.82
    min_rectangularity: float = 0.55
    min_width_ratio: float = 0.030
    min_height_ratio: float = 0.030
    max_aspect_ratio: float = 14.0
    min_ink_ratio: float = 0.018
    rescue_whole_page: bool = True


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_png(arr: np.ndarray, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)
    raw = path.read_bytes()
    return {"path": str(path), "relative_path": path.name, "sha256": sha256_bytes(raw), "size_bytes": len(raw)}


def arr_to_png_b64(arr: np.ndarray) -> str:
    bio = io.BytesIO()
    Image.fromarray(arr).save(bio, format="PNG")
    return base64.b64encode(bio.getvalue()).decode("ascii")


def bbox_xyxy_to_corners(bbox: list[float]) -> list[list[float]]:
    x0, y0, x1, y1 = bbox
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def bbox_from_poly(poly: list[list[float]]) -> list[float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


def normalize_quad(poly: list[list[float]]) -> list[list[float]]:
    pts = sorted(poly, key=lambda p: (p[1], p[0]))
    if len(pts) < 4:
        return bbox_xyxy_to_corners(bbox_from_poly(poly))
    top = sorted(pts[:2], key=lambda p: p[0])
    bottom = sorted(pts[-2:], key=lambda p: p[0])
    return [[float(top[0][0]), float(top[0][1])], [float(top[1][0]), float(top[1][1])], [float(bottom[1][0]), float(bottom[1][1])], [float(bottom[0][0]), float(bottom[0][1])]]


def polygon_area(poly: list[list[float]]) -> float:
    return float(abs(cv2.contourArea(np.array(poly, dtype=np.float32))))


def bbox_area(bbox: list[float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def iou_bbox(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = bbox_area(a) + bbox_area(b) - inter
    return 0.0 if union <= 0 else inter / union


def bbox_contains(parent: list[float], child: list[float], margin: float = 0.0) -> bool:
    px0, py0, px1, py1 = parent
    cx0, cy0, cx1, cy1 = child
    return cx0 >= px0 - margin and cy0 >= py0 - margin and cx1 <= px1 + margin and cy1 <= py1 + margin


def point_in_bbox(x: float, y: float, bbox: list[float], margin: float = 0.0) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin


def crop_region(arr: np.ndarray, bbox: list[float]) -> np.ndarray | None:
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = bbox
    x0 = max(0, min(w, int(round(x0))))
    y0 = max(0, min(h, int(round(y0))))
    x1 = max(0, min(w, int(round(x1))))
    y1 = max(0, min(h, int(round(y1))))
    if x1 <= x0 or y1 <= y0:
        return None
    return arr[y0:y1, x0:x1]


def crop_ink_ratio(gray: np.ndarray, bbox: list[float]) -> float:
    crop = crop_region(gray[..., None].repeat(3, axis=2), bbox)
    if crop is None:
        return 0.0
    g = crop[:, :, 0]
    return float((g < 235).mean())


def valid_panel_bbox(bbox: list[float], page_w: int, page_h: int, cfg: PanelDetectionConfig, gray: np.ndarray | None = None) -> bool:
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    if bw <= 0 or bh <= 0:
        return False
    if bw < page_w * cfg.min_width_ratio or bh < page_h * cfg.min_height_ratio:
        return False
    aspect = max(bw / max(1.0, bh), bh / max(1.0, bw))
    if aspect > cfg.max_aspect_ratio:
        return False
    area_ratio = bbox_area(bbox) / max(1.0, float(page_w * page_h))
    if area_ratio > cfg.max_area_ratio:
        return False
    if gray is not None and crop_ink_ratio(gray, bbox) < cfg.min_ink_ratio:
        return False
    return True


def render_pdf_pages(pdf_path: Path, zoom: float) -> list[tuple[int, np.ndarray, float, float]]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        pages.append((i, arr, float(pix.width), float(pix.height)))
    doc.close()
    return pages


def load_image_page(image_path: Path) -> tuple[int, np.ndarray, float, float]:
    arr = np.array(Image.open(image_path).convert("RGB"))
    h, w = arr.shape[:2]
    return 1, arr, float(w), float(h)


def extract_pdf_text_lines(pdf_path: Path, page_number: int, scale: float) -> list[TextLine]:
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    data = page.get_text("dict")
    out: list[TextLine] = []
    block_i = 0
    line_i = 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_i += 1
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            line_i += 1
            bbox = [float(v) * scale for v in line.get("bbox", [0, 0, 0, 0])]
            out.append(TextLine(id=f"P{page_number}_L{line_i}", page=page_number, text=text, bbox=bbox, source="pdf_native", block_no=block_i, reading_order=line_i))
    doc.close()
    return out


def get_paddle_engine(lang: str):
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception as e:
        raise RuntimeError("PaddleOCR is not installed. Run: pip install paddleocr paddlepaddle") from e

    attempts = [
        {"lang": lang, "use_textline_orientation": True},
        {"lang": lang, "use_angle_cls": True, "show_log": False},
        {"lang": lang, "use_angle_cls": True},
        {"lang": lang},
    ]
    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            return PaddleOCR(**kwargs)
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Could not initialize PaddleOCR for lang={lang}: {last_error}")


def _append_ocr_line(out: list[TextLine], page_number: int, text: str, bbox: list[float], confidence: float | None, source: str = "paddle_ocr") -> None:
    text = str(text).strip()
    if not text:
        return
    x0, y0, x1, y1 = [float(v) for v in bbox]
    if x1 <= x0 or y1 <= y0:
        return
    out.append(TextLine(
        id=f"P{page_number}_OCR_L{len(out) + 1}",
        page=page_number,
        text=text,
        bbox=[x0, y0, x1, y1],
        source=source,
        reading_order=len(out) + 1,
        confidence=confidence,
    ))


def extract_paddle_text_lines(arr: np.ndarray, page_number: int, engine: Any, image_path: Path | None = None, min_confidence: float = 0.20) -> list[TextLine]:
    """
    Mandatory text-layer OCR path.
    Supports FileMonster's high-success PaddleOCR 3.x predict() output and older 2.x ocr() output.
    Each Paddle textline becomes one independent SVG text-line object.
    """
    out: list[TextLine] = []

    if image_path is not None and hasattr(engine, "predict"):
        try:
            result = engine.predict(str(image_path))
            for page_result in result or []:
                if not isinstance(page_result, dict):
                    continue
                texts = page_result.get("rec_texts", []) or []
                scores = page_result.get("rec_scores", []) or []
                boxes = page_result.get("rec_boxes")
                polys = page_result.get("rec_polys")
                for i, text in enumerate(texts):
                    conf = float(scores[i]) if i < len(scores) else None
                    if conf is not None and conf < min_confidence:
                        continue
                    bbox = None
                    if boxes is not None and i < len(boxes):
                        vals = list(boxes[i])
                        if len(vals) >= 4:
                            bbox = [float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3])]
                    if bbox is None and polys is not None and i < len(polys):
                        xs = [float(p[0]) for p in polys[i]]
                        ys = [float(p[1]) for p in polys[i]]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]
                    if bbox is not None:
                        _append_ocr_line(out, page_number, text, bbox, conf, source="paddle_predict")
            if out:
                return out
        except Exception:
            out = []

    try:
        try:
            result = engine.ocr(arr, cls=True)
        except TypeError:
            result = engine.ocr(arr)
    except Exception:
        return out

    if not result:
        return out

    page_result = result[0] if isinstance(result, list) and len(result) == 1 and isinstance(result[0], list) else result
    for item in page_result:
        if not item or len(item) < 2:
            continue
        box, payload = item[0], item[1]
        text = ""
        conf = None
        if isinstance(payload, (list, tuple)) and payload:
            text = str(payload[0]).strip()
            if len(payload) > 1:
                try:
                    conf = float(payload[1])
                except Exception:
                    conf = None
        else:
            text = str(payload).strip()
        if conf is not None and conf < min_confidence:
            continue
        try:
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
        except Exception:
            continue
        _append_ocr_line(out, page_number, text, [min(xs), min(ys), max(xs), max(ys)], conf, source="paddle_ocr")
    return out


def find_runs(mask_1d: np.ndarray, min_len: int) -> list[tuple[int, int, float]]:
    runs = []
    start = None
    vals: list[float] = []
    for i, val in enumerate(mask_1d):
        if val > 0:
            if start is None:
                start = i; vals = []
            vals.append(float(val))
        elif start is not None:
            if i - start >= min_len:
                runs.append((start, i, float(np.mean(vals))))
            start = None; vals = []
    if start is not None and len(mask_1d) - start >= min_len:
        runs.append((start, len(mask_1d), float(np.mean(vals))))
    return runs


def detect_gutters(arr: np.ndarray) -> list[GutterBand]:
    h, w = arr.shape[:2]
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    bright = gray > 238
    dark = gray < 80
    row_bright, col_bright = bright.mean(axis=1), bright.mean(axis=0)
    row_dark, col_dark = dark.mean(axis=1), dark.mean(axis=0)
    row_score = np.where((row_bright > 0.72) & (row_dark < 0.08), row_bright - row_dark, 0.0)
    col_score = np.where((col_bright > 0.72) & (col_dark < 0.08), col_bright - col_dark, 0.0)
    min_h = max(8, int(h * 0.008)); min_w = max(8, int(w * 0.008))
    gutters: list[GutterBand] = []
    for i, (y0, y1, conf) in enumerate(find_runs(row_score, min_h), start=1):
        if y0 < h * 0.03 or y1 > h * 0.97: continue
        gutters.append(GutterBand(id=f"H_GUTTER_{i}", page=0, orientation="horizontal", bbox=[0.0, float(y0), float(w), float(y1)], confidence=float(min(1.0, conf))))
    for i, (x0, x1, conf) in enumerate(find_runs(col_score, min_w), start=1):
        if x0 < w * 0.03 or x1 > w * 0.97: continue
        gutters.append(GutterBand(id=f"V_GUTTER_{i}", page=0, orientation="vertical", bbox=[float(x0), 0.0, float(x1), float(h)], confidence=float(min(1.0, conf))))
    return gutters


def panel_cells_from_gutters(arr: np.ndarray, gutters: list[GutterBand], cfg: PanelDetectionConfig) -> list[dict[str, Any]]:
    h, w = arr.shape[:2]
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    xs = [0.0, float(w)]; ys = [0.0, float(h)]
    for g in gutters:
        x0, y0, x1, y1 = g.bbox
        if g.orientation == "horizontal": ys.append((y0 + y1) / 2.0)
        elif g.orientation == "vertical": xs.append((x0 + x1) / 2.0)
    xs = sorted(set(round(x, 2) for x in xs)); ys = sorted(set(round(y, 2) for y in ys))
    out = []
    pad = max(2.0, min(w, h) * 0.004)
    for row in range(len(ys) - 1):
        for col in range(len(xs) - 1):
            inner = [xs[col] + pad, ys[row] + pad, xs[col + 1] - pad, ys[row + 1] - pad]
            if not valid_panel_bbox(inner, w, h, cfg, gray):
                continue
            out.append({"bbox": inner, "polygon": bbox_xyxy_to_corners(inner), "area": bbox_area(inner), "confidence": min(1.0, 0.50 + crop_ink_ratio(gray, inner)), "source": "gutter_cell"})
    return out


def contour_passes(profile: str) -> list[dict[str, Any]]:
    if profile == "strict":
        return [
            {"name": "strict_large", "min_area_ratio": 0.010, "epsilon_ratio": 0.020, "canny1": 55, "canny2": 170, "dilate": 1, "close": 1},
            {"name": "strict_medium", "min_area_ratio": 0.006, "epsilon_ratio": 0.016, "canny1": 45, "canny2": 140, "dilate": 1, "close": 1},
        ]
    if profile == "loose":
        return [
            {"name": "loose_large", "min_area_ratio": 0.0030, "epsilon_ratio": 0.030, "canny1": 40, "canny2": 140, "dilate": 1, "close": 1},
            {"name": "loose_medium", "min_area_ratio": 0.0010, "epsilon_ratio": 0.022, "canny1": 28, "canny2": 105, "dilate": 2, "close": 1},
            {"name": "loose_small", "min_area_ratio": 0.00045, "epsilon_ratio": 0.016, "canny1": 18, "canny2": 75, "dilate": 2, "close": 2},
        ]
    if profile == "recall":
        return [
            {"name": "recall_large", "min_area_ratio": 0.0020, "epsilon_ratio": 0.035, "canny1": 35, "canny2": 130, "dilate": 1, "close": 1},
            {"name": "recall_medium", "min_area_ratio": 0.00070, "epsilon_ratio": 0.024, "canny1": 22, "canny2": 90, "dilate": 2, "close": 2},
            {"name": "recall_small", "min_area_ratio": 0.00022, "epsilon_ratio": 0.014, "canny1": 12, "canny2": 60, "dilate": 2, "close": 2},
            {"name": "recall_hairline", "min_area_ratio": 0.00015, "epsilon_ratio": 0.010, "canny1": 8, "canny2": 45, "dilate": 1, "close": 1},
        ]
    if profile == "comic":
        return [
            {"name": "large_panels", "min_area_ratio": 0.004, "epsilon_ratio": 0.028, "canny1": 45, "canny2": 150, "dilate": 1, "close": 1},
            {"name": "medium_panels", "min_area_ratio": 0.001, "epsilon_ratio": 0.018, "canny1": 30, "canny2": 110, "dilate": 2, "close": 1},
            {"name": "small_panels", "min_area_ratio": 0.00025, "epsilon_ratio": 0.012, "canny1": 20, "canny2": 85, "dilate": 2, "close": 2},
            {"name": "thin_edges", "min_area_ratio": 0.00020, "epsilon_ratio": 0.010, "canny1": 12, "canny2": 60, "dilate": 1, "close": 1},
        ]
    return [
        {"name": "balanced_large", "min_area_ratio": 0.004, "epsilon_ratio": 0.028, "canny1": 45, "canny2": 150, "dilate": 1, "close": 1},
        {"name": "balanced_medium", "min_area_ratio": 0.0015, "epsilon_ratio": 0.020, "canny1": 32, "canny2": 115, "dilate": 2, "close": 1},
        {"name": "balanced_small", "min_area_ratio": 0.00050, "epsilon_ratio": 0.014, "canny1": 20, "canny2": 80, "dilate": 2, "close": 1},
    ]


def contour_panel_candidates(arr: np.ndarray, cfg: PanelDetectionConfig) -> list[dict[str, Any]]:
    h, w = arr.shape[:2]
    page_area = float(w * h)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    out: list[dict[str, Any]] = []
    for p in contour_passes(cfg.profile):
        edges = cv2.Canny(blur, p["canny1"], p["canny2"])
        kernel = np.ones((3, 3), np.uint8)
        if p.get("close", 0):
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=p["close"])
        edges = cv2.dilate(edges, kernel, iterations=p["dilate"])
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            raw_area = cv2.contourArea(c)
            if raw_area < page_area * p["min_area_ratio"] or raw_area > page_area * cfg.max_area_ratio:
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, p["epsilon_ratio"] * peri, True)
            if len(approx) == 4:
                poly = normalize_quad([[float(pt[0][0]), float(pt[0][1])] for pt in approx])
            else:
                x, y, bw, bh = cv2.boundingRect(c)
                poly = bbox_xyxy_to_corners([float(x), float(y), float(x + bw), float(y + bh)])
            bbox = bbox_from_poly(poly)
            if not valid_panel_bbox(bbox, w, h, cfg, gray):
                continue
            rectangularity = polygon_area(poly) / max(1.0, bbox_area(bbox))
            if rectangularity < cfg.min_rectangularity:
                continue
            out.append({"bbox": bbox, "polygon": poly, "area": polygon_area(poly), "confidence": float(min(1.0, rectangularity)), "source": p["name"]})
    return out


def merge_candidates(candidates: list[dict[str, Any]], cfg: PanelDetectionConfig) -> list[dict[str, Any]]:
    if not candidates:
        return []
    scored = sorted(candidates, key=lambda c: (0 if c.get("source") == "gutter_cell" else 1, c.get("area", bbox_area(c["bbox"])), c.get("confidence", 0.0)), reverse=True)
    kept: list[dict[str, Any]] = []
    for cand in scored:
        bbox = cand["bbox"]
        skip = False
        for existing in kept:
            eb = existing["bbox"]
            if iou_bbox(bbox, eb) >= cfg.merge_iou:
                skip = True; break
            if bbox_contains(eb, bbox, margin=5) and bbox_area(bbox) < bbox_area(eb) * 0.92:
                skip = True; break
        if not skip:
            kept.append(cand)
    return sorted(kept, key=lambda r: (r["bbox"][1], r["bbox"][0]))


def name_panel(index: int, total: int) -> str:
    if total == 3:
        return ["top", "middle", "bottom"][index - 1]
    return f"panel_{index:02d}"


def manual_candidates_for_page(manual: dict[str, Any] | None, page_no: int) -> list[dict[str, Any]]:
    if not manual:
        return []
    pages = manual.get("pages", manual)
    vals = pages.get(str(page_no), pages.get(page_no, [])) if isinstance(pages, dict) else []
    out = []
    for i, item in enumerate(vals, start=1):
        if isinstance(item, dict):
            bbox = [float(v) for v in item.get("bbox", [])]
            name = item.get("name", f"manual_{i:02d}")
        else:
            bbox = [float(v) for v in item]
            name = f"manual_{i:02d}"
        if len(bbox) == 4:
            out.append({"bbox": bbox, "polygon": bbox_xyxy_to_corners(bbox), "area": bbox_area(bbox), "confidence": 1.0, "source": "manual", "manual_name": name})
    return out


def detect_panel_regions(arr: np.ndarray, page_no: int, cfg: PanelDetectionConfig, manual: dict[str, Any] | None = None) -> tuple[list[PanelRegion], list[GutterBand]]:
    h, w = arr.shape[:2]
    gutters = detect_gutters(arr)
    for g in gutters:
        g.page = page_no
        g.id = f"P{page_no}_{g.id}"
    manual_cands = manual_candidates_for_page(manual, page_no)
    if manual_cands:
        merged = merge_candidates(manual_cands, cfg)
    else:
        contour_cands = contour_panel_candidates(arr, cfg)
        gutter_cands = panel_cells_from_gutters(arr, gutters, cfg)
        if cfg.panel_source == "contours":
            merged = merge_candidates(contour_cands, cfg)
        elif cfg.panel_source == "gutters":
            merged = merge_candidates(gutter_cands, cfg)
        elif cfg.panel_source == "hybrid":
            merged = merge_candidates(contour_cands + gutter_cands, cfg)
        else:
            merged = merge_candidates(contour_cands, cfg)
            if len(merged) < 1:
                merged = merge_candidates(gutter_cands + contour_cands, cfg)
        if not merged and cfg.rescue_whole_page:
            pad = max(2.0, min(w, h) * 0.004)
            bbox = [pad, pad, float(w) - pad, float(h) - pad]
            merged = [{"bbox": bbox, "polygon": bbox_xyxy_to_corners(bbox), "area": bbox_area(bbox), "confidence": 0.25, "source": "whole_page_rescue"}]
    panels: list[PanelRegion] = []
    for i, cand in enumerate(merged, start=1):
        name = cand.get("manual_name") or name_panel(i, len(merged))
        pid = f"P{page_no}_{name.upper()}" if name in {"top", "middle", "bottom"} else f"P{page_no}_R{i}"
        polygon = cand.get("polygon") or bbox_xyxy_to_corners(cand["bbox"])
        corners = normalize_quad(polygon) if len(polygon) == 4 else bbox_xyxy_to_corners(cand["bbox"])
        panels.append(PanelRegion(id=pid, page=page_no, name=name, bbox=cand["bbox"], corners=corners, polygon=corners, reading_order=i, source=cand.get("source", "unknown"), confidence=float(cand.get("confidence", 0.0))))
    return panels, gutters


def assign_text_to_panels(lines: list[TextLine], panels: list[PanelRegion]) -> None:
    for line in lines:
        x0, y0, x1, y1 = line.bbox
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        matches = [p for p in panels if point_in_bbox(cx, cy, p.bbox, margin=3)]
        if matches:
            line.panel_id = sorted(matches, key=lambda p: bbox_area(p.bbox))[0].id


def path_for_svg(path_value: str | None) -> str:
    return html.escape(str(Path(path_value).resolve())) if path_value else ""


def svg_from_spatial_page(page_record: dict[str, Any], embed_panel_crops: bool, embed_page_b64: bool = False) -> str:
    width = float(page_record["width"]); height = float(page_record["height"]); page_no = int(page_record["page"])
    assets = page_record.get("assets", {})
    page_image = assets.get("page_image", {})
    if embed_page_b64 and page_image.get("path"):
        try:
            href = "data:image/png;base64," + base64.b64encode(Path(page_image["path"]).read_bytes()).decode("ascii")
        except Exception:
            href = path_for_svg(page_image.get("path"))
    else:
        href = path_for_svg(page_image.get("path"))
    out: list[str] = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" data-comica-page="{page_no}">')
    out.append('<metadata>')
    out.append(html.escape(json.dumps({"schema": "comica-page-svg", "source": "rebuilt_from_spatial_json", "page": page_no, "spatial_json": page_record.get("spatial_json", "")}, ensure_ascii=False)))
    out.append('</metadata>')
    out.append('<g id="page_reconstruction" class="page-reconstruction">')
    if href:
        out.append(f'<image id="page_background" class="page-background-object" href="{href}" x="0" y="0" width="{width}" height="{height}"/>')
    out.append('</g>')
    out.append('<g id="panel_assets" class="panel-assets">')
    for panel in page_record.get("panels", []):
        pid = html.escape(panel["id"]); x0, y0, x1, y1 = panel["bbox"]
        pts = " ".join(f"{x},{y}" for x, y in panel.get("polygon", panel.get("corners", [])))
        meta = html.escape(json.dumps(panel, ensure_ascii=False))
        order = html.escape(str(panel.get("reading_order", "")))
        out.append(f'<g id="{pid}" class="panel-object" data-panel-id="{pid}" data-reading-order="{order}">')
        out.append(f'<title>{meta}</title>')
        if embed_panel_crops and panel.get("crop_path"):
            out.append(f'<image id="{pid}_image_asset" class="panel-image-asset" href="{path_for_svg(panel.get("crop_path"))}" x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" opacity="1.0"/>')
        out.append(f'<polygon id="{pid}_bounds" class="panel-bounds-object" points="{pts}" fill="none" stroke="red" stroke-width="3" opacity="0.95"/>')
        out.append(f'<text id="{pid}_label" class="panel-label-object" x="{x0}" y="{max(14, y0 - 6)}" font-family="Arial" font-size="14" fill="red">{html.escape(panel.get("name", pid))}</text>')
        out.append('</g>')
    out.append('</g>')
    out.append('<g id="gutter_objects" class="gutter-objects">')
    for g in page_record.get("gutters", []):
        x0, y0, x1, y1 = g["bbox"]; gid = html.escape(g["id"])
        out.append(f'<g id="{gid}" class="gutter-object" data-orientation="{html.escape(g.get("orientation", ""))}">')
        out.append(f'<title>{html.escape(json.dumps(g, ensure_ascii=False))}</title>')
        out.append(f'<rect id="{gid}_rect" x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="yellow" opacity="0.18"/>')
        out.append('</g>')
    out.append('</g>')
    out.append('<g id="text_line_objects" class="text-line-objects">')
    for line in page_record.get("text_lines", []):
        if not line.get("text"): continue
        tid = html.escape(line["id"]); x0, y0, x1, y1 = line["bbox"]
        font_size = max(5.0, (y1 - y0) * 0.75)
        out.append(f'<g id="{tid}" class="text-line-object" data-text-id="{tid}" data-panel-id="{html.escape(line.get("panel_id") or "")}">')
        out.append(f'<title>{html.escape(json.dumps(line, ensure_ascii=False))}</title>')
        out.append(f'<rect id="{tid}_bbox" class="text-line-bbox-object" x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="blue" stroke-width="0.5" opacity="0.35"/>')
        out.append(f'<text id="{tid}_text" class="text-line-text-object" x="{x0}" y="{y1}" font-family="Arial, sans-serif" font-size="{font_size}" fill="blue">{html.escape(line.get("text", ""))}</text>')
        out.append('</g>')
    out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


def print_progress(prefix: str, current: int, total: int, detail: str = "") -> None:
    pct = 100.0 if total <= 0 else (current / total) * 100.0
    msg = f"[comica] {prefix} {current}/{total} ({pct:6.2f}%)"
    if detail: msg += f" | {detail}"
    print(msg, flush=True)


def collect_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.rglob("*")) if p.suffix.lower() in (IMAGE_EXTS | PDF_EXTS)]


def load_manual_panels(path: str | None) -> dict[str, Any] | None:
    if not path: return None
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def process_file(path: Path, out_root: Path, pdf_zoom: float, embed_panel_crops: bool, panel_cfg: PanelDetectionConfig, ocr_mode: str, ocr_lang: str, prefer_ocr: bool, manual: dict[str, Any] | None, file_index: int, file_total: int, embed_page_b64: bool, require_text_layer: bool, native_text_min_chars: int, min_ocr_confidence: float) -> dict[str, Any]:
    file_out = out_root / path.stem
    panels_dir = file_out / "panels"; svg_dir = file_out / "svg"; spatial_dir = file_out / "spatial_json"; pages_dir = file_out / "pages"
    for d in (panels_dir, svg_dir, spatial_dir, pages_dir): d.mkdir(parents=True, exist_ok=True)
    is_pdf = path.suffix.lower() in PDF_EXTS
    pages = render_pdf_pages(path, pdf_zoom) if is_pdf else [load_image_page(path)]
    engine = get_paddle_engine(ocr_lang) if ocr_mode == "paddle" else None
    page_records: list[dict[str, Any]] = []
    total_pages = len(pages)
    print_progress(f"file {file_index}/{file_total} start", 0, max(1, total_pages), path.name)
    for page_no, arr, width, height in pages:
        print_progress(f"file {file_index}/{file_total} page", page_no, total_pages, "rendered; detecting panels")
        page_path = pages_dir / f"page_{page_no:04d}.png"
        page_saved = save_png(arr, page_path)
        panels, gutters = detect_panel_regions(arr, page_no, panel_cfg, manual=manual)
        pdf_lines = extract_pdf_text_lines(path, page_no, pdf_zoom) if is_pdf else []
        native_chars = sum(len(t.text.strip()) for t in pdf_lines)
        native_text_is_weak = native_chars < native_text_min_chars
        ocr_lines: list[TextLine] = []

        should_run_ocr = engine is not None and (prefer_ocr or native_text_is_weak or not pdf_lines or not is_pdf)
        if should_run_ocr:
            reason = "prefer_ocr" if prefer_ocr else (f"native_text_weak chars={native_chars}" if native_text_is_weak else "image_or_no_native_text")
            print_progress(f"file {file_index}/{file_total} page", page_no, total_pages, f"running PaddleOCR ({reason})")
            ocr_lines = extract_paddle_text_lines(arr, page_no, engine, image_path=page_path, min_confidence=min_ocr_confidence)

        if prefer_ocr and ocr_lines:
            text_lines = ocr_lines
        elif pdf_lines and not native_text_is_weak:
            text_lines = pdf_lines
        elif ocr_lines:
            text_lines = ocr_lines
        else:
            text_lines = pdf_lines

        if require_text_layer and not text_lines:
            print_progress(f"file {file_index}/{file_total} page", page_no, total_pages, "WARNING text_lines=0; Paddle could not see text or OCR is unavailable")

        assign_text_to_panels(text_lines, panels)
        for p in panels:
            crop = crop_region(arr, p.bbox)
            if crop is None: continue
            crop_path = panels_dir / f"page_{page_no:04d}_{p.name}.png"
            saved = save_png(crop, crop_path)
            p.crop_path = saved["path"]; p.crop_sha256 = saved["sha256"]; p.crop_size_bytes = saved["size_bytes"]
        page_record = {
            "schema": {"name": "comica-spatial-page", "version": SCHEMA_VERSION},
            "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
            "created_utc": now_utc(),
            "source_file": str(path),
            "page": page_no,
            "width": width,
            "height": height,
            "coordinate_space": "rendered_page_pixels",
            "pdf_zoom": pdf_zoom if is_pdf else None,
            "assets": {"page_image": page_saved},
            "panels": [asdict(p) for p in panels],
            "gutters": [asdict(g) for g in gutters],
            "text_lines": [asdict(t) for t in text_lines],
            "relationships": [{"relationship_type": "text_inside_panel", "text_id": t.id, "panel_id": t.panel_id, "text": t.text, "bbox": t.bbox} for t in text_lines],
        }
        page_json_path = spatial_dir / f"page_{page_no:04d}.comica.page.json"
        page_record["spatial_json"] = str(page_json_path)
        write_json(page_json_path, page_record)
        svg = svg_from_spatial_page(page_record, embed_panel_crops=embed_panel_crops, embed_page_b64=embed_page_b64)
        svg_path = svg_dir / f"page_{page_no:04d}.comica.svg"
        svg_path.write_text(svg, encoding="utf-8")
        page_record["svg"] = str(svg_path)
        write_json(page_json_path, page_record)
        page_records.append({**page_record, "page_image_b64": None})
        print_progress(f"file {file_index}/{file_total} page", page_no, total_pages, f"panels={len(panels)} gutters={len(gutters)} text_lines={len(text_lines)} svg={svg_path.name}")
    manifest = {
        "schema": {"name": "comica-extract", "version": SCHEMA_VERSION},
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_utc": now_utc(),
        "source": {"path": str(path), "name": path.name, "type": "pdf" if is_pdf else "image", "sha256": sha256_file(path)},
        "output_directory": str(file_out),
        "panel_detection": asdict(panel_cfg),
        "ocr": {"mode": ocr_mode, "lang": ocr_lang, "prefer_ocr": prefer_ocr, "require_text_layer": require_text_layer, "native_text_min_chars": native_text_min_chars, "min_ocr_confidence": min_ocr_confidence},
        "spatial_model": {"source_of_truth": "spatial_json/page_*.comica.page.json", "svg_rebuilt_from_json": True},
        "pages": page_records,
    }
    write_json(file_out / "comica.json", manifest)
    print_progress(f"file {file_index}/{file_total} done", total_pages, max(1, total_pages), f"{path.name} | panels={sum(len(p['panels']) for p in page_records)} text_lines={sum(len(p['text_lines']) for p in page_records)}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Comica: faithful page SVG reconstruction from spatial JSON, with editable panel/text/gutter objects.")
    parser.add_argument("input", help="Input PDF, image, or folder")
    parser.add_argument("-o", "--output-dir", default="comica_out", help="Output directory")
    parser.add_argument("--pdf-zoom", type=float, default=2.0, help="PDF render zoom. Try 1.5, 2, 3, or 4; different zooms produce different panel results")
    parser.add_argument("--panel-profile", default="balanced", choices=["strict", "balanced", "loose", "recall", "comic"], help="strict=fewer/cleaner, balanced=FileMonster-like, loose/recall=more aggressive")
    parser.add_argument("--panel-source", default="fallback", choices=["contours", "gutters", "fallback", "hybrid"], help="contours=FileMonster-style, gutters=gutter grid only, fallback=contours first, hybrid=both")
    parser.add_argument("--max-area-ratio", type=float, default=0.94)
    parser.add_argument("--merge-iou", type=float, default=0.82)
    parser.add_argument("--min-rectangularity", type=float, default=0.55)
    parser.add_argument("--min-width-ratio", type=float, default=0.030)
    parser.add_argument("--min-height-ratio", type=float, default=0.030)
    parser.add_argument("--max-aspect-ratio", type=float, default=14.0)
    parser.add_argument("--min-ink-ratio", type=float, default=0.018)
    parser.add_argument("--no-rescue-whole-page", action="store_true", help="Disable full-page fallback panel when no panels are found")
    parser.add_argument("--manual-panels", help="Optional JSON with user-specified panel boxes per page")
    parser.add_argument("--ocr", default="auto", choices=["auto", "none", "paddle"], help="auto=mandatory text layer: use PDF-native text when strong, otherwise PaddleOCR; paddle=force PaddleOCR availability; none=disable OCR")
    parser.add_argument("--ocr-lang", default="en", help="PaddleOCR language, e.g. en, ch, japan, korean")
    parser.add_argument("--prefer-ocr", action="store_true", help="Prefer PaddleOCR text over PDF-native text")
    parser.add_argument("--no-require-text-layer", action="store_true", help="Allow pages to finish with zero text objects without warning")
    parser.add_argument("--native-text-min-chars", type=int, default=12, help="If PDF-native text chars/page is below this, treat it as weak and run PaddleOCR")
    parser.add_argument("--min-ocr-confidence", type=float, default=0.20, help="Minimum PaddleOCR confidence for keeping a text-line object")
    parser.add_argument("--no-panel-crop-embed", action="store_true", help="Do not place panel crop image references inside SVG panel groups")
    parser.add_argument("--embed-page-b64", action="store_true", help="Embed full page image inside SVG instead of linking to page PNG")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve(); out_root = Path(args.output_dir).expanduser().resolve(); out_root.mkdir(parents=True, exist_ok=True)
    panel_cfg = PanelDetectionConfig(profile=args.panel_profile, panel_source=args.panel_source, max_area_ratio=args.max_area_ratio, merge_iou=args.merge_iou, min_rectangularity=args.min_rectangularity, min_width_ratio=args.min_width_ratio, min_height_ratio=args.min_height_ratio, max_aspect_ratio=args.max_aspect_ratio, min_ink_ratio=args.min_ink_ratio, rescue_whole_page=not args.no_rescue_whole_page)
    manual = load_manual_panels(args.manual_panels)
    files = collect_inputs(input_path)
    if not files: raise SystemExit(f"No comic PDF/image files found: {input_path}")
    print("[comica] goals: faithful per-page SVG, JSON spatial source of truth, editable panel/gutter/text objects, mandatory line-by-line text extraction, tunable panel detection", flush=True)
    run_files = []
    for idx, f in enumerate(files, start=1):
        ocr_mode = args.ocr
        if ocr_mode == "auto":
            ocr_mode = "paddle" if not args.no_require_text_layer else "none"
        manifest = process_file(
            f, out_root, args.pdf_zoom, not args.no_panel_crop_embed, panel_cfg,
            ocr_mode, args.ocr_lang, args.prefer_ocr, manual, idx, len(files),
            args.embed_page_b64, require_text_layer=not args.no_require_text_layer,
            native_text_min_chars=args.native_text_min_chars, min_ocr_confidence=args.min_ocr_confidence
        )
        run_files.append({"source": manifest["source"], "output_directory": manifest["output_directory"], "page_count": len(manifest["pages"]), "panel_count": sum(len(p["panels"]) for p in manifest["pages"]), "gutter_count": sum(len(p["gutters"]) for p in manifest["pages"]), "text_line_count": sum(len(p["text_lines"]) for p in manifest["pages"])})
    run_manifest = {"schema": {"name": "comica-run", "version": SCHEMA_VERSION}, "tool": {"name": TOOL_NAME, "version": TOOL_VERSION}, "created_utc": now_utc(), "input": str(input_path), "output_directory": str(out_root), "files": run_files}
    write_json(out_root / "comica_run.json", run_manifest)
    print("\nComica extraction complete.", flush=True)
    print(f"Files:        {len(run_files)}", flush=True)
    print(f"Output:       {out_root}", flush=True)
    print(f"Run manifest: {out_root / 'comica_run.json'}", flush=True)


if __name__ == "__main__":
    main()
