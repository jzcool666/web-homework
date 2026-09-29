/**
 * 题库与练习页面的纯换算（SPEC-009）。
 *
 * 判分完全由服务器完成；这里的函数只用于展示与表单状态：
 * 选项勾选、答案集合比较、状态与题型文案、幂等提交前的规范化。
 */

export const QUESTION_TYPE_LABEL = {
  single: '单选题',
  multiple: '多选题',
  boolean: '判断题',
}

export const DIFFICULTY_LABEL = {
  1: '基础',
  2: '进阶',
  3: '挑战',
}

export const ASSESSMENT_STATE_LABEL = {
  draft: '草稿',
  upcoming: '未开始',
  open: '进行中',
  closed: '已结束',
}

export const SUBMISSION_STATUS_LABEL = {
  draft: '草稿',
  submitted: '已提交',
}

export const KIND_LABEL = {
  practice: '自练',
  quiz: '随堂测',
  homework: '作业',
  exam: '考试',
}

/** 选项 key 的默认序列：A、B、C…… */
export function nextOptionKey(keys = []) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  for (const letter of alphabet) {
    if (!keys.includes(letter)) return letter
  }
  return `K${keys.length + 1}`
}

/** 判断题固定 true/false 两个选项。 */
export function defaultOptions(type) {
  if (type === 'boolean') {
    return [
      { key: 'true', label: '正确' },
      { key: 'false', label: '错误' },
    ]
  }
  return [
    { key: 'A', label: '' },
    { key: 'B', label: '' },
  ]
}

/** 单选/判断只能有一个答案，多选可多个；切换题型时裁剪旧答案。 */
export function normalizeAnswer(type, answer, optionKeys) {
  const valid = (answer ?? []).filter((key) => optionKeys.includes(key))
  if (type === 'multiple') return valid
  return valid.slice(0, 1)
}

/** 勾选/取消一个选项，按题型决定是否互斥。 */
export function toggleSelection(selected, key, multiple) {
  const current = selected ?? []
  if (!multiple) return current.includes(key) ? [] : [key]
  return current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
}

/** 与服务器一致：集合完全相同才算答对。 */
export function isCorrectSelection(selected, answer) {
  const left = new Set(selected ?? [])
  const right = new Set(answer ?? [])
  if (left.size === 0) return false
  if (left.size !== right.size) return false
  for (const key of left) {
    if (!right.has(key)) return false
  }
  return true
}

/** 从提交的 answers 中取某题已保存的选项。 */
export function selectedFor(answers, itemId) {
  return (answers ?? []).find((entry) => entry.item_id === itemId)?.selected ?? []
}

/** 是否全部题目都已作答（仅用于提示，不阻止提交）。 */
export function unansweredCount(items, answers) {
  return (items ?? []).filter((item) => selectedFor(answers, item.id).length === 0).length
}

/** 分数展示：反馈未公开时服务端返回 null。 */
export function formatScore(score, total) {
  if (score === null || score === undefined) return '待公开'
  return `${score} / ${total}`
}

/** 选项 key → 文案，用于结果页回显答案。 */
export function optionLabel(options, key) {
  return (options ?? []).find((option) => option.key === key)?.label ?? key
}

export function selectionText(options, keys) {
  if (!keys || keys.length === 0) return '未作答'
  return keys.map((key) => optionLabel(options, key)).join('、')
}
