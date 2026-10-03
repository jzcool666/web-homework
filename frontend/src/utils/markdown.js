/**
 * Markdown 安全渲染（SPEC-005 第 4 节第 2 条、ADR-008）。
 *
 * 设计原则：**先转义、再生成**。整段输入先做 HTML 转义，原始 HTML 因此不可能
 * 变成标记；只有本文件显式生成的标签才会出现在结果里。链接只接受 http/https，
 * 其余（javascript:、data:、file:）原样显示为文本，不生成 <a>。
 *
 * 支持子集：标题、段落、无序/有序列表、引用、表格、围栏代码块、行内代码、
 * 加粗、斜体、链接。不支持原始 HTML——这正是要求。
 */

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

const CODE_SPAN = '\u0001'
const BLOCK = '\u0000'

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ESCAPES[ch])
}

/** 只放行 http/https；返回 null 表示不能作为链接输出。 */
export function safeUrl(raw) {
  const url = String(raw ?? '').trim()
  return /^https?:\/\/[^\s]+$/i.test(url) ? url : null
}

function renderInline(text) {
  const codes = []
  let out = text.replace(/`([^`]+)`/g, (_match, code) => {
    codes.push(`<code>${code}</code>`)
    return `${CODE_SPAN}${codes.length - 1}${CODE_SPAN}`
  })

  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
    const href = safeUrl(url)
    if (!href) return match
    return `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`
  })

  return out.replace(new RegExp(`${CODE_SPAN}(\\d+)${CODE_SPAN}`, 'g'), (_m, i) => codes[Number(i)])
}

function splitRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => renderInline(cell.trim()))
}

const TABLE_SEPARATOR = /^\s*\|[\s:|-]+\|\s*$/
const TABLE_ROW = /^\s*\|.*\|\s*$/
const UNORDERED = /^\s*[-*]\s+/
const ORDERED = /^\s*\d+\.\s+/
const HEADING = /^(#{1,6})\s+(.*)$/
// 块级判定在转义之后进行，因此引用符号是 &gt;（见文件头「先转义、再生成」）
const QUOTE = /^\s*&gt;\s?/

function isBlockStart(line) {
  return (
    new RegExp(`^${BLOCK}\\d+${BLOCK}$`).test(line) ||
    HEADING.test(line) ||
    QUOTE.test(line) ||
    UNORDERED.test(line) ||
    ORDERED.test(line) ||
    TABLE_ROW.test(line)
  )
}

function renderTable(lines, start) {
  const header = splitRow(lines[start])
  let index = start + 2
  const rows = []
  while (index < lines.length && TABLE_ROW.test(lines[index])) {
    rows.push(splitRow(lines[index]))
    index += 1
  }
  const head = header.map((cell) => `<th>${cell}</th>`).join('')
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`)
    .join('')
  return { html: `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`, next: index }
}

function renderList(lines, start, pattern, tag) {
  let index = start
  const items = []
  while (index < lines.length && pattern.test(lines[index])) {
    items.push(renderInline(lines[index].replace(pattern, '')))
    index += 1
  }
  const body = items.map((item) => `<li>${item}</li>`).join('')
  return { html: `<${tag}>${body}</${tag}>`, next: index }
}

/**
 * 把 Markdown 子集渲染成可安全放进 v-html 的 HTML 字符串。
 * 输入里的一切都先被转义，原始 HTML 与脚本不会执行。
 */
export function renderMarkdown(source) {
  const normalized = String(source ?? '').replace(/\r\n?/g, '\n')

  // 围栏代码块先摘出来，避免其内容被当作正文标记处理
  const fences = []
  const stripped = normalized.replace(/```([^\n`]*)\n([\s\S]*?)```/g, (_m, lang, body) => {
    const language = escapeHtml(lang.trim())
    const attribute = language ? ` class="language-${language}"` : ''
    fences.push(`<pre><code${attribute}>${escapeHtml(body.replace(/\n$/, ''))}</code></pre>`)
    return `${BLOCK}${fences.length - 1}${BLOCK}`
  })

  const lines = escapeHtml(stripped).split('\n')
  const html = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (/^\s*$/.test(line)) {
      i += 1
      continue
    }

    const fence = new RegExp(`^${BLOCK}(\\d+)${BLOCK}$`).exec(line)
    if (fence) {
      html.push(fences[Number(fence[1])])
      i += 1
      continue
    }

    const heading = HEADING.exec(line)
    if (heading) {
      const level = heading[1].length
      html.push(`<h${level}>${renderInline(heading[2].trim())}</h${level}>`)
      i += 1
      continue
    }

    if (QUOTE.test(line)) {
      const quoted = []
      while (i < lines.length && QUOTE.test(lines[i])) {
        quoted.push(renderInline(lines[i].replace(QUOTE, '')))
        i += 1
      }
      html.push(`<blockquote>${quoted.join('<br>')}</blockquote>`)
      continue
    }

    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1])) {
      const table = renderTable(lines, i)
      html.push(table.html)
      i = table.next
      continue
    }

    if (UNORDERED.test(line)) {
      const list = renderList(lines, i, UNORDERED, 'ul')
      html.push(list.html)
      i = list.next
      continue
    }

    if (ORDERED.test(line)) {
      const list = renderList(lines, i, ORDERED, 'ol')
      html.push(list.html)
      i = list.next
      continue
    }

    const paragraph = []
    while (i < lines.length && !/^\s*$/.test(lines[i]) && !isBlockStart(lines[i])) {
      paragraph.push(lines[i])
      i += 1
    }
    html.push(`<p>${paragraph.map((part) => renderInline(part)).join('<br>')}</p>`)
  }

  return html.join('\n')
}
