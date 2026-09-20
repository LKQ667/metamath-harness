# 英文文风与加粗规则 (math-paper-en)

本文件规定论文可见论述的英文写作纪律，由 `check_paper_prose_style.py` 与 `check_paper_emphasis.py` 校验。

## 1. 禁止与限制的表达

- 禁止机械枚举与总结套话: Firstly、Secondly、Thirdly、First of all、Last but not least、In conclusion、To sum up、As we all know。
- 以下过渡与强调短语全文合计不超过 6 次: Moreover,、Furthermore,、In addition,、It is worth noting that、It is important to note that、It is obvious that、Obviously,、Clearly,、Needless to say。
- 单个短语出现 3 次及以上直接判为套话。
- 禁止 obviously 或 clearly 式的无依据跳步；每一步用变量、条件、数据或图表承接。
- 可见论述括号密度不得超过每千词 6 组 (圆括号、方括号与全角括号合计)。
- 论文可见论述不得出现中文字符。

## 2. 段落功能

每段只承担一个明确功能，并按"结论 -> 证据 -> 边界"的顺序推进: 先给这一段的判断，再给支撑它的公式、数据或图表，最后说明适用条件与例外。删除重复定义、同义复述、空泛承接与模板化三段式；不删变量定义、适用条件、推导桥梁、误差说明与边界讨论。

## 3. 加粗规则

- Summary Sheet: 每一问使用 `\paperstrong{For Problem N}` 只加粗标签短语；标签后的标点与正文不得进入同一粗体命令；Keywords 行每个关键词分别加粗。
- 正文: 只加粗决定性模型名、关键判据、核心数值结论与最终推荐中的短语；正文加粗密度不超过每百词 3 处。
- 任何加粗跨度不得超过 60 字符，不得是完整句 (以句号结尾或内部含句末加句首空格的结构一律判错)。
- 加粗内容不得含中文；不要用连续多句、整段或逐段机械加粗。

## 4. 交付前自检

1. 逐段复读，标出每段的功能类型 (定义、推导、结果、解释、边界)，功能重复的段落合并。
2. 检查是否存在只换连接词的重复论证；检查结论是否越过证据边界。
3. 检查每个图表后是否紧跟解释其含义与结论的段落。
4. 检查括号密度、加粗密度与 Three-round self review 记录一致。