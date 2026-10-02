"""SPEC-017 识别辅助的图像处理（E069/E070）。

流程按 SPEC-017 第 4 节与 ADR-007 第 6 条：Pillow 解码 → 灰度化 → Otsu 二值化 →
检测规则网格线 → 切分单元格并移除边框 → 把格内字符归一化后与 0/1 模板比对 →
按列位序（Q3Q2Q1Q0）组装状态序列 → 由相邻行推导次态转换对。

- 只用传统图像处理，不使用深度学习模型，也不访问外部服务。
- 模板用 OpenCV 内置的 Hershey 字体绘制，不依赖系统字体文件，因此同图同参可复现。
- 单格判定要求最高匹配度 ≥ 0.80 且与次优候选的差 ≥ 0.10，否则判为不确定、不猜测。
- 输入固定为格式 v1：白底黑线规则网格，恰好 4 列、2—17 行，格边长 ≥ 40 像素。
"""

from __future__ import annotations

import io
import time

import cv2
import numpy as np
from PIL import Image

FORMAT_VERSION = "state_table_v1"

# 归一化画布：模板与待判字符都缩放到这个尺寸后再比 IoU
CANON_WIDTH, CANON_HEIGHT = 24, 32

# 网格线判定：占比接近最大值的行/列才算线，避免把对齐的笔画误判成线
GRID_PEAK_RATIO = 0.6
GRID_MIN_RATIO = 0.5

CELL_MARGIN_PX = 6
MIN_CELL_SIZE = 40
EXPECTED_COLUMNS = 4
MIN_ROWS, MAX_ROWS = 2, 17

MIN_MATCH = 0.80
MIN_MATCH_MARGIN = 0.10

REASON_DECODE = "图片无法解码"
REASON_GRID = "未检测到网格"
REASON_SHAPE = "行列数不符"
REASON_CELL = "格内非 0/1"
REASON_UNCERTAIN = "字符不确定"

CODE_DECODE = "IMAGE_DECODE_FAILED"
CODE_GRID = "GRID_NOT_DETECTED"
CODE_SHAPE = "SHAPE_MISMATCH"
CODE_CELL = "CELL_NOT_BINARY"
CODE_UNCERTAIN = "CELL_UNCERTAIN"


class RecognitionTimeout(RuntimeError):
    """超过配置的处理限时。调用方据此返回 503 且不保留任务。"""


class RecognitionFormatError(RuntimeError):
    """输入不符合格式 v1；带 APIC 约定的原因码与说明。"""

    def __init__(self, code: str, reason: str, details=None):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.details = details


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise RecognitionTimeout("识别超时")


def decode_image(payload: bytes) -> np.ndarray:
    """Pillow 解码为 8 位灰度数组。解码失败按格式失败处理，不抛 500。"""
    try:
        with Image.open(io.BytesIO(payload)) as image:
            gray = image.convert("L")
            return np.array(gray, dtype=np.uint8)
    except Exception as exc:  # Pillow 的解码异常种类较多
        raise RecognitionFormatError(CODE_DECODE, REASON_DECODE) from exc


def binarize(gray: np.ndarray) -> np.ndarray:
    """Otsu 二值化并反相：墨迹（网格线与字符）为 255。"""
    if gray.size == 0:
        raise RecognitionFormatError(CODE_GRID, REASON_GRID)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return ink


def detect_lines(profile: np.ndarray) -> list[int]:
    """把墨迹占比接近峰值的行/列聚成网格线中心下标。"""
    if profile.size == 0:
        return []
    threshold = max(GRID_MIN_RATIO, float(profile.max()) * GRID_PEAK_RATIO)
    hot = profile > threshold
    lines: list[int] = []
    start: int | None = None
    for index, value in enumerate(hot):
        if value and start is None:
            start = index
        elif not value and start is not None:
            lines.append((start + index - 1) // 2)
            start = None
    if start is not None:
        lines.append((start + len(hot) - 1) // 2)
    return lines


def render_glyph(char: str) -> np.ndarray:
    """用 OpenCV 内置 Hershey 字体把 0/1 画到画布再归一化，作为比对模板。"""
    canvas = np.zeros((CANON_HEIGHT * 3, CANON_WIDTH * 3), dtype=np.uint8)
    scale, thickness = 3.0, 7
    (width, height), _ = cv2.getTextSize(char, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    origin = ((canvas.shape[1] - width) // 2, (canvas.shape[0] + height) // 2)
    cv2.putText(
        canvas, char, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, 255, thickness, cv2.LINE_AA
    )
    return normalize_glyph(canvas)


def normalize_glyph(mask: np.ndarray) -> np.ndarray:
    """裁到墨迹外接框，等比缩放进固定画布并居中；没有墨迹时返回全零。"""
    output = np.zeros((CANON_HEIGHT, CANON_WIDTH), dtype=np.uint8)
    points = cv2.findNonZero(mask)
    if points is None:
        return output
    x, y, width, height = cv2.boundingRect(points)
    crop = mask[y : y + height, x : x + width]
    scale = min(CANON_WIDTH / width, CANON_HEIGHT / height)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    resized = cv2.resize(crop, (new_width, new_height), interpolation=cv2.INTER_AREA)
    resized = (resized > 127).astype(np.uint8)
    dx, dy = (CANON_WIDTH - new_width) // 2, (CANON_HEIGHT - new_height) // 2
    output[dy : dy + new_height, dx : dx + new_width] = resized
    return output


def glyph_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """两个归一化字形掩码的交并比。"""
    union = int(np.logical_or(left, right).sum())
    if union == 0:
        return 0.0
    return float(np.logical_and(left, right).sum() / union)


def build_templates() -> dict[str, np.ndarray]:
    return {bit: render_glyph(bit) for bit in ("0", "1")}


def classify_cell(cell: np.ndarray, templates: dict[str, np.ndarray]) -> tuple[str, dict]:
    """判定单格是 0 还是 1；不确定时抛格式错误。"""
    glyph = normalize_glyph(cell)
    scores = {bit: glyph_similarity(glyph, template) for bit, template in templates.items()}
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    best_bit, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    if best_score < MIN_MATCH:
        raise RecognitionFormatError(
            CODE_CELL,
            REASON_CELL,
            {"match": round(best_score, 4), "required": MIN_MATCH},
        )
    if best_score - runner_up < MIN_MATCH_MARGIN:
        raise RecognitionFormatError(
            CODE_UNCERTAIN,
            REASON_UNCERTAIN,
            {"best": round(best_score, 4), "runner_up": round(runner_up, 4)},
        )
    return best_bit, scores


def recognize_state_table(payload: bytes, *, deadline: float | None = None) -> dict:
    """识别格式 v1 的状态表。返回 {"status": "done", "result": ...} 或
    {"status": "failed", "error": {...}}；超时抛 RecognitionTimeout。"""
    _check_deadline(deadline)
    gray = decode_image(payload)
    ink = binarize(gray)
    _check_deadline(deadline)

    row_lines = detect_lines((ink > 0).mean(axis=1))
    column_lines = detect_lines((ink > 0).mean(axis=0))
    if len(row_lines) < 2 or len(column_lines) < 2:
        return _failure(CODE_GRID, REASON_GRID, {"row_lines": len(row_lines), "col_lines": len(column_lines)})
    if len(column_lines) != EXPECTED_COLUMNS + 1:
        return _failure(
            CODE_SHAPE,
            REASON_SHAPE,
            {"columns": len(column_lines) - 1, "expected_columns": EXPECTED_COLUMNS},
        )
    rows = len(row_lines) - 1
    if not (MIN_ROWS <= rows <= MAX_ROWS):
        return _failure(
            CODE_SHAPE,
            REASON_SHAPE,
            {"rows": rows, "allowed_rows": [MIN_ROWS, MAX_ROWS]},
        )

    # 单元格必须够大，否则说明图不是格式 v1 的规格
    cell_sizes = [
        min(row_lines[i + 1] - row_lines[i], column_lines[j + 1] - column_lines[j])
        for i in range(rows)
        for j in range(EXPECTED_COLUMNS)
    ]
    if min(cell_sizes) - 2 * CELL_MARGIN_PX < MIN_CELL_SIZE // 2:
        return _failure(
            CODE_SHAPE,
            REASON_SHAPE,
            {"cell_size": min(cell_sizes), "min_cell_size": MIN_CELL_SIZE},
        )

    templates = build_templates()
    values: list[int] = []
    scores: list[float] = []
    for row in range(rows):
        _check_deadline(deadline)
        bits = []
        for column in range(EXPECTED_COLUMNS):
            y0 = row_lines[row] + CELL_MARGIN_PX
            y1 = row_lines[row + 1] - CELL_MARGIN_PX
            x0 = column_lines[column] + CELL_MARGIN_PX
            x1 = column_lines[column + 1] - CELL_MARGIN_PX
            cell = ink[y0:y1, x0:x1]
            try:
                bit, cell_scores = classify_cell(cell, templates)
            except RecognitionFormatError as exc:
                details = {"row": row, "column": column, **(exc.details or {})}
                return _failure(exc.code, exc.reason, details)
            bits.append(bit)
            scores.append(max(cell_scores.values()))
        # 位序 Q3Q2Q1Q0：最左列是高位
        values.append(int("".join(bits), 2))

    return {
        "status": "done",
        "result": {
            "rows": rows,
            "cols": EXPECTED_COLUMNS,
            "states": [{"row": index, "value": value} for index, value in enumerate(values)],
            "transitions": [
                {"from": values[index], "to": values[index + 1]}
                for index in range(len(values) - 1)
            ],
            "confidence": round(min(scores), 4),
            "requires_review": True,
        },
    }


def _failure(code: str, reason: str, details=None) -> dict:
    return {
        "status": "failed",
        "error": {"code": code, "message": reason, "details": details or {}},
    }


__all__ = [
    "FORMAT_VERSION",
    "RecognitionFormatError",
    "RecognitionTimeout",
    "binarize",
    "build_templates",
    "classify_cell",
    "decode_image",
    "detect_lines",
    "glyph_similarity",
    "normalize_glyph",
    "recognize_state_table",
    "render_glyph",
]
