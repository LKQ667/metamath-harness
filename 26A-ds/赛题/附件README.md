# 多核调度赛题最终评估代码

"华为杯"数学建模比赛A题评估代码

## 最常用的四条命令

在项目根目录运行：

```powershell
python code/stub_multicore_cut_and_schedule.py <计算图.json> -n 4
python code/multicore_cut_evaluate_problem_1.py <计算图.json> <方案.json> --config data/config.txt
python code/multicore_cut_evaluate_problem_2.py <计算图.json> <方案.json> --config data/config.txt
python code/multicore_cut_evaluate_problem_3.py <计算图.json> <方案.json> --config data/config.txt
```

省略 `<方案.json>` 时，脚本读取与计算图同目录的
`<计算图文件名>_multicore_res.json`。每个评估器输出结果 JSON、简短日志和
Perfetto Trace。`stub_multicore_cut_and_schedule.py` 只演示方案格式，不是
基线算法。

## 从输入到 makespan 的完整流程

1. **读取选手方案。** `derive_multicore_plan` 校验每个计算操作属于且只属于
   一个子图，并检查每个子图只安排到一个核心。
   同时校验原图格式、唯一 ID、有效端点、非负 cycles/size，以及原始完整图
   无环（包括 COPY 节点和同一子图内部的依赖）。
2. **形成 Task。** 问题 1 把每个子图作为一个 Task；问题 2、3 把同一核心
   上的子图合并为一个 Task。跨 Task 或跨核心的数据边会生成 COPY。
3. **执行核内调度。** `schedule_step1` 生成拓扑访问顺序；
   `schedule_step2` 在容量不足时插入换出和换入操作；`schedule_step3`
   完成乱序排布并输出每条 Pipe 的确定顺序。
4. **补偿地址依赖。** Step3 不求具体地址，而把 L1/UB 容量抽象成可拆分的
   虚拟字节额度。额度再次用于新输出前，旧 tensor 的全部读者必须完成；
   这些 WAR/WAW 关系作为直接 op→op 边写入执行图。额度可拆分和合并，
   因而不产生地址碎片，也不需要在比赛中加入内存整理算法。
5. **事件模拟。** 三个评估器直接装载 Step3 的执行图和逐 Pipe 顺序。
   在启动事件循环前，问题1检查数据依赖与同核Task顺序的组合图；问题2/3
   检查本地执行依赖、Pipe FIFO与跨核COPY组成的全局操作图，拒绝等待环。
   模拟器完成已结束操作、推进 Pipe、释放新满足的真实数据依赖与内存复用
   依赖、发射各 Pipe 的队首操作，然后跳到最近的下一事件时刻。
6. **统计结果。** 最晚结束时刻是 makespan，同时输出每核时间线、片上内存
   峰值、COPY 流量以及题三的 Cache 统计。

## 选手入口与错误处理

选手调用三个问题评估器、`singlecore_evaluate.py` 或方案示例生成器。
非法输入会返回非零退出码并在stderr输出 `[EVALUATION ERROR]`，不生成
新的成功结果/Trace。若方案存在全局等待环，会在模拟开始前报告
`dependency cycle` 及带类型的环边；Python异常的 `cycle` 属性保留完整环。

原图必须包含 `ops`、`tensors`、`edges` 三个列表；op/tensor ID为非负整数，
共享ID空间且唯一，边端点必须存在，禁止重复边和tensor→tensor直接边。
每个 op 必须带 `pipe` 字段，且取值属于四条 Pipe 之一；仿真与调度都直接读
该字段，不按 op 名称猜测 Pipe。op 名称本身不做白名单校验。
配置项拼写错误、重复键、未知段、无效数值以及重复JSON键都会明确报错，
不静默回退；显式 `--config` 指向不存在的文件也报错。

## 配置来源

评估用到的全部参数来自 `config.txt`，代码中不设默认值；配置缺失时脚本直接
报错退出，不会用固定数值算出成绩。

|配置段|键|含义|是否必需|
|---|---|---|---|
|`[capacity]`|`L1` `UB`|片上 L1/UB 容量（字节）|必需|
|`[bandwidth]`|`bandwidth`|DDR↔片上搬运带宽（字节/周期）|必需|
|`[multicore_scene_a]`|`task_cross_core_wait_cycles` `task_same_core_wait_cycles`|题目 1 的 Task 等待|题目 1 必需|
|`[multicore_scene_b]`|`cross_core_copy_delay_cycles`|题目 2/3 的跨核 COPY 等待|题目 2/3 必需|
|`[problem_3]`|`cache_capacity_bytes` `cache_bandwidth_bytes_per_cycle`|题目 3 的 Cache 容量与命中带宽|题目 3 必需|

未指定 `--config` 时按"计算图所在目录/config.txt"查找，找不到就报
`configuration file not found`。段名只接受上表中的五个，出现未知段（例如
拼写错误，或已不再支持的 `[pipe_capacity]`）会报 `unknown section`，不会被
静默忽略。

`schedule_step1/2/3` 是内部算法接口，前序保证的DAG、拓扑序、ID唯一性和
参数约束写在函数入口注释中，不再次校验。只有重排或跨核组合引入的新约束
才需要新的检查；Step3保留自身新生成内存依赖的输出契约检查。

## 文件列表

|文件|作用|建议阅读对象|
|---|---|---|
|`contest_io.py`|统一命令行、JSON、日志和 Trace|想了解输入输出的同学|
|`evaluation_validation.py`|选手输入及全局执行依赖校验|理解不可执行方案的诊断|
|`multicore_cut_evaluate_problem_1.py`|问题 1：每子图一个 Task|解答问题 1|
|`multicore_cut_evaluate_problem_2.py`|问题 2：每核心一个 Task|解答问题 2|
|`multicore_cut_evaluate_problem_3.py`|问题 3：增加只读 FIFO Cache|解答问题 3|
|`schedule_step1.py`|无环图的核内访问顺序|理解拓扑调度|
|`schedule_step2.py`|片上容量与 Spill 插入|理解内存约束|
|`schedule_step3.py`|乱序排布、逐 Pipe 顺序和内存复用补边|理解执行依赖|
|`stub_multicore_cut_and_schedule.py`|方案格式校验及随机示例|第一次运行代码|
|`singlecore_evaluate.py`|单核基线|计算加速比|
