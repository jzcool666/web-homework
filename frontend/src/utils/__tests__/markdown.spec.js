/**
 * SPEC-005 T-005-02：含 script 的内容渲染不得执行，Markdown 禁原始 HTML。
 *
 * 断言方式：渲染结果里不允许出现可执行的标签（script/iframe/on* 事件属性），
 * 且原始 HTML 必须以转义文本形式出现。
 */

import { describe, expect, it } from 'vitest'

import { renderMarkdown, safeUrl } from '@/utils/markdown'

const EXECUTABLE = /<(script|iframe|object|embed|svg|img|style)\b/i

/** 解析后的文档里不允许有任何 on* 事件属性（转义后的文本不算）。 */
function liveEventAttributes(html) {
  const host = document.createElement('div')
  host.innerHTML = html
  const found = []
  for (const element of host.querySelectorAll('*')) {
    for (const attribute of element.attributes) {
      if (/^on/i.test(attribute.name)) found.push(attribute.name)
    }
  }
  return found
}

function renderWithDom(source) {
  const host = document.createElement('div')
  host.innerHTML = renderMarkdown(source)
  return host
}

describe('renderMarkdown 安全边界', () => {
  it('把 script 标签渲染为文本，不产生 script 元素', () => {
    const html = renderMarkdown('正常内容\n\n<script>window.__pwned = 1<\/script>')
    expect(html).not.toMatch(EXECUTABLE)
    expect(html).toContain('&lt;script&gt;')

    const dom = renderWithDom('正常内容\n\n<script>window.__pwned = 1<\/script>')
    expect(dom.querySelectorAll('script')).toHaveLength(0)
    expect(globalThis.__pwned).toBeUndefined()
  })

  it('丢弃 img/svg 的 on* 事件属性', () => {
    const source = '<img src=x onerror=alert(1)>\n\n<svg onload=alert(1)></svg>'
    const html = renderMarkdown(source)
    expect(html).not.toMatch(EXECUTABLE)
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')

    // 转义后的文本里虽然含 "onerror=" 字样，但解析后不存在任何元素或事件属性
    const dom = renderWithDom(source)
    expect(dom.querySelectorAll('img, svg')).toHaveLength(0)
    expect(liveEventAttributes(html)).toEqual([])
  })

  it('只把 http/https 链接渲染成 a 标签', () => {
    const html = renderMarkdown('[安全](https://example.org/a?x=1&y=2)')
    expect(html).toContain('<a href="https://example.org/a?x=1&amp;y=2"')
    expect(html).toContain('rel="noopener noreferrer"')

    for (const bad of [
      '[x](javascript:alert(1))',
      '[x](JaVaScRiPt:alert(1))',
      '[x](data:text/html;base64,PHNjcmlwdD4=)',
      '[x](file:///etc/passwd)',
    ]) {
      const rendered = renderMarkdown(bad)
      expect(rendered).not.toContain('<a ')
      expect(liveEventAttributes(rendered)).toEqual([])
    }
  })

  it('safeUrl 仅放行 http/https 且不含空白', () => {
    expect(safeUrl('https://example.org')).toBe('https://example.org')
    expect(safeUrl('HTTP://example.org')).toBe('HTTP://example.org')
    expect(safeUrl('javascript:alert(1)')).toBeNull()
    expect(safeUrl(' /\tjavascript:alert(1)')).toBeNull()
    expect(safeUrl('https://example.org/a b')).toBeNull()
  })

  it('围栏代码块内的标记不被解释为 HTML', () => {
    const html = renderMarkdown('```\n<script>alert(1)</script>\n```')
    expect(html).toContain('<pre><code>')
    expect(html).not.toMatch(EXECUTABLE)
    const dom = renderWithDom('```\n<script>alert(1)</script>\n```')
    expect(dom.querySelectorAll('script')).toHaveLength(0)
  })

  it('行内代码中的尖括号同样被转义', () => {
    const html = renderMarkdown('复位为 `<script>` 时按文本显示')
    expect(html).toContain('<code>&lt;script&gt;</code>')
    expect(html).not.toMatch(EXECUTABLE)
  })
})

describe('renderMarkdown 子集渲染', () => {
  it('渲染标题、加粗、列表与引用', () => {
    const html = renderMarkdown(
      '## 位序约定\n\n- 串行输入从 Q3 进入\n- 数据向 Q0 方向移动\n\n> 引用一行\n\n**重点**',
    )
    expect(html).toContain('<h2>位序约定</h2>')
    expect(html).toContain('<li>串行输入从 Q3 进入</li>')
    expect(html).toContain('<blockquote>引用一行</blockquote>')
    expect(html).toContain('<strong>重点</strong>')
  })

  it('渲染有序列表与状态表', () => {
    const html = renderMarkdown(
      '1. 写出激励表达式\n2. 代入当前状态\n\n| J | K | Q(t+1) |\n| --- | --- | --- |\n| 1 | 1 | 翻转 |\n',
    )
    expect(html).toContain('<ol><li>写出激励表达式</li><li>代入当前状态</li></ol>')
    expect(html).toContain('<th>J</th>')
    expect(html).toContain('<td>翻转</td>')
  })

  it('空内容渲染为空字符串', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
  })
})
