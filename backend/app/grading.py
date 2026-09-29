"""SPEC-009 纯规则：题目结构校验、判分与投影。

这里不依赖 Flask，也不碰数据库，便于直接单测：
- 选项 key 唯一；单选一个答案，多选至少两个正确项，判断只有 true/false。
- selected 集合与答案集合完全相同才得该题全部分，空答案 0 分。
"""

from __future__ import annotations

from .models_assessment import (
    TYPE_BOOLEAN,
    TYPE_MULTIPLE,
    TYPE_SINGLE,
)

OPTION_COUNT_MIN = 2
OPTION_COUNT_MAX = 6
STEM_MAX = 10000
KNOWLEDGE_MIN = 1
KNOWLEDGE_MAX = 3


class FieldError(ValueError):
    """字段级校验失败；调用方负责翻译成 422 VALIDATION_ERROR。"""

    def __init__(self, field: str, rule: str):
        super().__init__(f"{field}: {rule}")
        self.field = field
        self.rule = rule


def parse_options(raw, question_type: str) -> list[dict]:
    """校验并标准化选项列表。"""
    if not isinstance(raw, list):
        raise FieldError("options", "必须是选项数组")
    options: list[dict] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise FieldError("options", "每个选项必须是对象")
        key = entry.get("key")
        label = entry.get("label")
        if not isinstance(key, str) or not key:
            raise FieldError("options", "选项 key 必须是非空字符串")
        if not isinstance(label, str) or not label:
            raise FieldError("options", "选项 label 必须是非空字符串")
        if key in seen:
            raise FieldError("options", "选项 key 必须唯一")
        seen.add(key)
        options.append({"key": key, "label": label})

    if question_type == TYPE_BOOLEAN:
        if seen != {"true", "false"}:
            raise FieldError("options", "判断题的选项 key 只能是 true/false")
        return options

    if not (OPTION_COUNT_MIN <= len(options) <= OPTION_COUNT_MAX):
        raise FieldError("options", f"选项数量必须在 {OPTION_COUNT_MIN}—{OPTION_COUNT_MAX} 之间")
    return options


def parse_answer(raw, question_type: str, option_keys: list[str]) -> list[str]:
    """校验并标准化答案；返回去重后的 key 列表。"""
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise FieldError("answer", "答案必须是字符串数组")
    unique = list(dict.fromkeys(raw))
    unknown = [key for key in unique if key not in option_keys]
    if unknown:
        raise FieldError("answer", f"答案不在选项内：{','.join(unknown)}")

    if question_type == TYPE_SINGLE and len(unique) != 1:
        raise FieldError("answer", "单选题必须有且只有一个答案")
    if question_type == TYPE_MULTIPLE and len(unique) < 2:
        raise FieldError("answer", "多选题至少两个正确项")
    if question_type == TYPE_BOOLEAN and len(unique) != 1:
        raise FieldError("answer", "判断题必须有且只有一个答案")
    return unique


def grade_selected(selected, answer) -> bool:
    """selected 与 answer 集合完全相同才算答对；空答案一律错误。"""
    selected_set = {item for item in (selected or []) if isinstance(item, str)}
    if not selected_set:
        return False
    return selected_set == {item for item in (answer or []) if isinstance(item, str)}


def validate_selected(selected, option_keys: list[str]) -> list[str]:
    """校验作答选项；非法 key 是客户端错误（422），数量不作限制。

    数量不设限是有意为之：多选少选、单选多选都按「集合不完全相同」判 0 分，
    而不是拒绝保存，这样学生仍能看到自己的原始作答。
    """
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        raise FieldError("selected", "必须是字符串数组")
    unique = list(dict.fromkeys(selected))
    unknown = [key for key in unique if key not in set(option_keys)]
    if unknown:
        raise FieldError("selected", f"选项不存在：{','.join(unknown)}")
    return unique


def build_snapshot(question, knowledge_ids, knowledge_titles) -> dict:
    """发布时冻结的题目快照：完整题目版本、答案、解析与知识点 ID/名称。"""
    return {
        "question_id": question.id,
        "version": question.version,
        "type": question.type,
        "stem_md": question.stem_md,
        "options": question.options,
        "answer": question.answer,
        "explanation_md": question.explanation_md,
        "difficulty": question.difficulty,
        "knowledge_ids": list(knowledge_ids),
        "knowledge_titles": list(knowledge_titles),
    }


def score_submission(items, answers_by_item) -> tuple[int, dict[int, tuple[bool, int]]]:
    """按快照判分；返回 (总分, {item_id: (correct, awarded_points)})。"""
    total = 0
    graded: dict[int, tuple[bool, int]] = {}
    for item in items:
        snapshot = item.snapshot
        selected = answers_by_item.get(item.id, [])
        correct = grade_selected(selected, snapshot.get("answer", []))
        awarded = item.points if correct else 0
        graded[item.id] = (correct, awarded)
        total += awarded
    return total, graded
