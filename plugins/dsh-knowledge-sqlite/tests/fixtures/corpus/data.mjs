// 实验测试集：编码 agent 跨会话记忆场景
// 每条记忆：id + 原文（写入时的内容）
// 每个查询：目标记忆 id + 用户改写后的问法（刻意不含原文显著词汇）
// 全部为"难查询"：与原文无显著词法重叠，模拟真实用户的口语化/模糊描述

export const memories = [
  {
    id: 'm1',
    text: '部署流程是 pnpm build 之后运行 pnpm dsh web，浏览器访问 127.0.0.1:3080。',
  },
  {
    id: 'm2',
    text: 'ctx.knowledge 的记忆检索默认用 SQLite 的 FTS 索引，relevance 分量走 BM25 词法打分。',
  },
  {
    id: 'm3',
    text: 'node_modules 和 .dsh 目录不能提交到 git，它们属于构建生成物，应该写进 .gitignore。',
  },
  {
    id: 'm4',
    text: 'approval 策略已经从 ask 改成了 never，bash 沙箱执行命令时不会再弹确认框。',
  },
  {
    id: 'm5',
    text: '工作区切到 deepseekharnesstest 之后，之前的会话日志仍然能用 session-query 的全文索引搜到。',
  },
  {
    id: 'm6',
    text: '富化字段里最重要的是一组"未来可能被问到的问法"，它决定了同义改写查询的命中率。',
  },
  {
    id: 'm7',
    text: 'agent 预设的 persona 写在 standard 预设的 agent.cordis.yml 里，想改要复制一份预设再编辑。',
  },
  {
    id: 'm8',
    text: 'web 模式下 tool-bash 是禁用的，shell 工具都改由 agent 预设在自己的 realm 里挂载。',
  },
  {
    id: 'm9',
    text: '计划模式不允许改文件，只能先探索、再提交完整方案等人批准。',
  },
  {
    id: 'm10',
    text: 'sandbox 的默认权限是 workspace-write，只有危险全开模式才不会弹确认。',
  },
  {
    id: 'm11',
    text: 'skill 的会话目录只展示名字和一行描述，完整正文要模型主动调用 skill 工具才加载。',
  },
  {
    id: 'm12',
    text: 'goals 工具用于长任务跟踪，会话重启后处于暂停状态，需要用户说继续才会恢复执行。',
  },
]

export const queries = [
  { id: 'q1', target: 'm1', text: '怎么把这个项目跑起来' },
  { id: 'q2', target: 'm1', text: '本地网页服务在哪个端口' },
  { id: 'q3', target: 'm2', text: '记忆功能搜东西的原理是什么' },
  { id: 'q4', target: 'm3', text: '哪些文件不用管版本控制' },
  { id: 'q5', target: 'm4', text: '现在执行命令还要不要人点头' },
  { id: 'q6', target: 'm5', text: '换目录后旧对话记录还能找到吗' },
  { id: 'q7', target: 'm6', text: '为什么换个说法也能搜到' },
  { id: 'q8', target: 'm7', text: '想改机器人的自我介绍该动哪个文件' },
  { id: 'q9', target: 'm8', text: '浏览器界面里怎么没有终端工具' },
  { id: 'q10', target: 'm9', text: '只做方案不动代码的模式怎么开' },
  { id: 'q11', target: 'm10', text: '文件操作默认能写哪些地方' },
  { id: 'q12', target: 'm11', text: '技能清单为什么只给一行介绍' },
  { id: 'q13', target: 'm12', text: '长跑的任务中断了怎么接着干' },
  { id: 'q14', target: 'm4', text: '不用确认是不是更危险' },
]
