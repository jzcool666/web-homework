import { bitsOf, formatBits } from '@/utils/demo'

// Teaching copy and projections of committed server events, never a second simulator.
export const MODEL_LESSONS = {
  d: { title: '把一个输入，记住一拍', caption: 'D 触发器', description: '拨动 D，观察它何时真正写入 Q。', focus: '输入会立即变化；记忆只在时钟上升沿更新。', icon: '记', color: '#5275eb' },
  jk: { title: '两路输入，四种动作', caption: 'JK 触发器', description: '保持、清零、置位、翻转，一拍一拍看清楚。', focus: 'J、K 决定动作，时钟上升沿决定动作何时发生。', icon: '换', color: '#8b65d8' },
  counter: { title: '让每一拍，都走一步', caption: '4 位计数器', description: '跟着亮起的状态，理解计数、保持和回零。', focus: '状态轨迹显示当前所在位置；输出灯显示同一状态的二进制。', icon: '数', color: '#1c9997' },
  shift: { title: '看见数据逐格移动', caption: '4 位移位寄存器', description: '串行输入从 Q3 进入，原来的数据向右移动。', focus: '每个格子存一位；EN=1、RESET=0 时，每个有效上升沿向右移一格。', icon: '移', color: '#da9055' },
}

export function describeCommittedEvent(row, type) {
  if (!row) return { title: '等待第一拍', text: '先设置输入，再点击「前进一步」。观察输入、时钟和输出之间的关系。', tone: 'idle' }
  const before = formatBits(row.q_before ?? 0, type)
  const after = formatBits(row.q ?? 0, type)
  if (row.op === 'set') return { title: '输入改变，记忆保持', text: `输入开关已经改变，但没有产生上升沿，Q 仍为 ${after}。`, tone: 'hold' }
  if (!row.rising) return { title: '下降沿，输出保持', text: `CLK 从 1 回到 0。这不是有效沿，Q 仍为 ${after}。`, tone: 'hold' }
  const inputs = row.inputs ?? {}
  let reason = ''
  if (inputs.reset) reason = 'RESET=1，同步复位在这一上升沿生效。'
  else if (type === 'd') reason = `D=${inputs.d ?? 0} 在这一上升沿被采样并写入 Q。`
  else if (type === 'jk') {
    const action = { '00': '保持', '01': '清零', '10': '置位', '11': '翻转' }[`${inputs.j ?? 0}${inputs.k ?? 0}`]
    reason = `J=${inputs.j ?? 0}、K=${inputs.k ?? 0}，本拍执行「${action}」。`
  } else if (!inputs.enable) reason = 'EN=0，计数 / 移位暂停，本拍保持原状态。'
  else if (type === 'counter') reason = row.q === 0 && row.q_before > 0 ? '计数状态回到 0，开始下一轮。' : 'EN=1，本拍完成一次计数。'
  else reason = `SI=${inputs.serial_in ?? 0} 进入 Q3，原 Q3→Q2、Q2→Q1、Q1→Q0，原 Q0 移出。`
  return { title: `第 ${row.step_no} 拍 · 有效上升沿`, text: `${reason} 已执行：${before} → ${after}。`, tone: 'rise' }
}

export function committedShiftTokens(row) {
  if (!row?.rising || row.inputs?.reset || !row.inputs?.enable) return []
  return [row.inputs.serial_in ?? 0, ...bitsOf(row.q_before ?? 0, 'shift')]
}
