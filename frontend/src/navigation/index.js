// Only routes already implemented are clickable. Planned entries keep the
// information architecture visible without claiming a Spec is complete.
export const roleLabels = {
  student: '学生空间',
  teacher: '教师空间',
  admin: '管理空间',
}

export const navigation = {
  student: [
    { label: '学习首页', icon: 'home', route: 'home' },
    { label: '课程学习与收藏', icon: 'book', route: 'student-learning', activeRoutes: ['student-learning', 'student-knowledge'] },
    { label: '考勤与请假', icon: 'calendar', route: 'student-classroom' },
    { label: '我的课堂', icon: 'clock', route: 'student-demos', activeRoutes: ['student-demos', 'student-demo'] },
    {
      label: '习题训练',
      icon: 'check',
      route: 'student-practice',
      activeRoutes: ['student-practice', 'student-assessment', 'student-result', 'student-mistakes'],
    },
    {
      label: '实验中心',
      icon: 'flask',
      route: 'student-experiments',
      activeRoutes: ['student-experiments', 'student-experiment', 'student-attempts'],
    },
    { label: '学习分析', icon: 'chart', planned: 'SPEC-006' },
    { label: '课程问答', icon: 'spark', route: 'student-qa' },
    { label: '知识图谱', icon: 'network', planned: 'SPEC-016' },
  ],
  teacher: [
    { label: '教学首页', icon: 'home', route: 'home' },
    { label: '课堂', icon: 'clock', route: 'teacher-classroom', activeRoutes: ['teacher-classroom', 'teacher-demo', 'teacher-demo-present'] },
    { label: '备课', icon: 'book', route: 'teacher-lesson-plans' },
    { label: '课程内容', icon: 'layers', route: 'teacher-content' },
    { label: '题库', icon: 'check', route: 'teacher-questions' },
    {
      label: '测评与讲评',
      icon: 'chart',
      route: 'teacher-assessments',
      activeRoutes: ['teacher-assessments', 'teacher-assessment'],
    },
    { label: '实验', icon: 'flask', planned: 'SPEC-013 教师端' },
    { label: '实验统计', icon: 'chart', route: 'teacher-experiment-stats' },
    { label: '考勤与请假', icon: 'calendar', route: 'teacher-attendance' },
    { label: '出勤统计', icon: 'chart', route: 'teacher-attendance-analytics' },
    { label: '学情分析', icon: 'chart', route: 'teacher-learning-analytics' },
    { label: '智能组卷', icon: 'spark', route: 'teacher-paper-generation' },
    { label: '课程问答', icon: 'spark', route: 'teacher-qa' },
  ],
  admin: [
    { label: '管理首页', icon: 'home', route: 'home' },
    { label: '课程内容', icon: 'book', route: 'teacher-content' },
    { label: '账号管理', icon: 'people', route: 'admin-users' },
    { label: '班级管理', icon: 'layers', route: 'admin-classes', activeRoutes: ['admin-classes', 'admin-enrollments'] },
  ],
}

export function navigationFor(role) {
  return navigation[role] ?? []
}
