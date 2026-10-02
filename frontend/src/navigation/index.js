// Only routes already implemented are clickable. Planned entries keep the
// information architecture visible without claiming a Spec is complete.
export const roleLabels = {
  student: '学生空间',
  teacher: '教师空间',
  admin: '管理空间',
}

export const navigation = {
  student: [
    { label: '学习首页', icon: 'home', route: 'home', group: '学习' },
    {
      label: '课程学习与收藏',
      icon: 'book',
      route: 'student-learning',
      activeRoutes: ['student-learning', 'student-knowledge'],
      group: '学习',
    },
    {
      label: '我的课堂',
      icon: 'clock',
      route: 'student-demos',
      activeRoutes: ['student-demos', 'student-demo'],
      group: '学习',
    },
    { label: '考勤与请假', icon: 'calendar', route: 'student-classroom', group: '学习' },
    {
      label: '习题训练',
      icon: 'check',
      route: 'student-practice',
      activeRoutes: ['student-practice', 'student-assessment', 'student-result', 'student-mistakes'],
      group: '练习与实验',
    },
    {
      label: '实验中心',
      icon: 'flask',
      route: 'student-experiments',
      activeRoutes: ['student-experiments', 'student-experiment', 'student-attempts'],
      group: '练习与实验',
    },
    { label: '状态表识别', icon: 'flask', route: 'student-recognition', group: '练习与实验' },
    { label: '复习推荐', icon: 'spark', route: 'student-recommendations', group: '学习提升' },
    { label: '学习分析', icon: 'chart', planned: 'SPEC-006', group: '学习提升' },
    { label: '课程问答', icon: 'spark', route: 'student-qa', group: '学习提升' },
    { label: '知识图谱', icon: 'network', route: 'knowledge-graph', group: '学习提升' },
  ],
  teacher: [
    { label: '教学首页', icon: 'home', route: 'home', group: '核心教学' },
    {
      label: '课堂',
      icon: 'clock',
      route: 'teacher-classroom',
      activeRoutes: ['teacher-classroom', 'teacher-demo', 'teacher-demo-present'],
      group: '核心教学',
    },
    { label: '备课', icon: 'book', route: 'teacher-lesson-plans', group: '核心教学' },
    { label: '课程内容', icon: 'layers', route: 'teacher-content', group: '内容与测评' },
    { label: '题库', icon: 'check', route: 'teacher-questions', group: '内容与测评' },
    {
      label: '测评与讲评',
      icon: 'chart',
      route: 'teacher-assessments',
      activeRoutes: ['teacher-assessments', 'teacher-assessment'],
      group: '内容与测评',
    },
    { label: '实验', icon: 'flask', planned: 'SPEC-013 教师端', group: '内容与测评' },
    {
      label: '学情分析',
      icon: 'chart',
      route: 'teacher-learning-analytics',
      group: '数据分析',
    },
    { label: '实验统计', icon: 'chart', route: 'teacher-experiment-stats', group: '数据分析' },
    {
      label: '出勤统计',
      icon: 'chart',
      route: 'teacher-attendance-analytics',
      group: '数据分析',
    },
    { label: '学习预警', icon: 'chart', route: 'teacher-warnings', group: '数据分析' },
    { label: '智能组卷', icon: 'spark', route: 'teacher-paper-generation', group: '智能工具' },
    { label: '课程问答', icon: 'spark', route: 'teacher-qa', group: '智能工具' },
    { label: '知识图谱', icon: 'network', route: 'knowledge-graph', group: '智能工具' },
    { label: '考勤与请假', icon: 'calendar', route: 'teacher-attendance', group: '课堂管理' },
  ],
  admin: [
    { label: '管理首页', icon: 'home', route: 'home' },
    { label: '课程内容', icon: 'book', route: 'teacher-content' },
    { label: '账号管理', icon: 'people', route: 'admin-users' },
    {
      label: '班级管理',
      icon: 'layers',
      route: 'admin-classes',
      activeRoutes: ['admin-classes', 'admin-enrollments'],
    },
  ],
}

// Group order is explicit so the sidebar order does not depend on array order.
export const navigationGroups = {
  student: ['学习', '练习与实验', '学习提升'],
  teacher: ['核心教学', '内容与测评', '数据分析', '智能工具', '课堂管理'],
}

export function navigationFor(role) {
  return navigation[role] ?? []
}

/** Items grouped for the sidebar; roles without a group spec stay a single flat group. */
export function groupedNavigationFor(role) {
  const items = navigationFor(role)
  if (items.length === 0) return []

  const order = navigationGroups[role]
  if (!order) return [{ label: null, items }]

  const groups = order.map((label) => ({
    label,
    items: items.filter((item) => item.group === label),
  }))
  // An item whose group is missing from the order must not silently disappear.
  const ungrouped = items.filter((item) => !order.includes(item.group))
  if (ungrouped.length > 0) groups.push({ label: null, items: ungrouped })

  return groups.filter((group) => group.items.length > 0)
}
