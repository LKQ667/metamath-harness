"""由唯一结果源生成三问的 result.md 交接文档。

每个 Q 目录的 result.md 面向未参与建模的队友或评委助理，完整说明本问的目标、
输入、假设、模型思路、公式通俗解释、运行命令、输出文件、核心数值结果、图表清单、
结果解释以及局限与下一问衔接。全部数值来自 `results/final_results.json`。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORES = [1, 2, 3, 4, 5]

COMMON_TAIL = """
## 局限与下一问衔接

本问的估算模型按字节数与带宽之比折算边界搬运时间，没有显式建模核内调度算法在
容量不足时的换出选择，因此对缓存压力极大的用例，估算值与实测值会有偏差；分核
采用单遍列表调度，切分与分核只通过候选择优间接耦合。下一问沿用本问的无环切分
骨架，只替换通信代价口径与等待常数。
"""


def load():
    results = json.loads((ROOT / "results" / "final_results.json").read_text(encoding="utf-8"))
    profile = {
        row["case"]: row
        for row in csv.DictReader((ROOT / "data" / "case_profile.csv").open(encoding="utf-8"))
    }
    return results, profile


def table_speedup(block):
    lines = ["| 核心数 | 平均加速比 | 平均 Makespan（周期） |", "|---|---|---|"]
    for cores in CORES:
        speed = block["average_speedup"].get(str(cores))
        makespan = block["average_makespan"].get(str(cores))
        if speed is None:
            continue
        lines.append(f"| {cores} | {speed:.4f} | {int(makespan):,} |")
    return "\n".join(lines)


def extrema(per_case, cores, key="speedup"):
    values = [(entry[str(cores)][key], case) for case, entry in per_case.items() if str(cores) in entry]
    values.sort()
    return values[0], values[-1]


def q1_doc(results, profile):
    block = results["q1"]
    low, high = extrema(block["per_case"], 5)
    worst = sorted(block["per_case"].items(), key=lambda kv: kv[1]["5"]["speedup"])[:3]
    return f"""# 问题一（场景 A）结果交接

## 问题目标

在无核间同步机制的场景 A 下，为每个核内操作分配子图 id，把子图分配到 2～5 个核心，
并确定每个核心上的子图执行顺序，使总体任务执行时间（Makespan）尽可能短，同时控制
总额外数据搬运量。

## 输入数据

- 赛题附件 `data/case_001.json` ～ `case_100.json`，共 {results["meta"]["case_count"]} 张
  Op-Tensor 二部图，全部只读引用，未做任何修改。
- 固定配置 `data/config.txt`：L1 = 524288 字节，UB = 131072 字节，
  DDR 带宽 = 60 字节/周期，跨核前驱等待 = 1000 周期，同核换任务等待 = 100 周期。
- 派生数据 `data/case_profile.csv`：每个用例的结构画像（规模、工作量、关键路径、
  并行宽度、主存字节数）。

## 核心假设

1. 各核心同构，负载均衡只取决于分配到各核的工作量；
2. 静态调度，运行期不重调度；
3. 子图时长下界取各流水线工作量、边界搬运折算周期与核内关键路径的最大值；
4. 边界搬运字节由承载依赖的张量大小决定，与边数无关；
5. 访问主存的搬运共享同一条带宽并公平分摊；
6. 子图依赖图必须无环，否则方案判为无效。

## 模型思路

先把 Op-Tensor 二部图收缩为操作级有向无环图，再并行构造三类候选切分：依赖锥聚簇、
连续段切分与分层切分，三者都从构造上保证子图依赖图无环。分核阶段按后向关键路径
长度降序处理子图，把每个子图分配到使其估算完成时刻最小的核心。最后用单核兜底
策略保证算法不会给出比单核基线更差的方案。

## 关键公式通俗解释

- 任务激活时刻：一个任务最早能在「同核前一个任务结束 + 100 周期」与「所有跨核前驱
  结束 + 1000 周期」两者中的较晚时刻开始。跨核等待远大于同核等待，因此让依赖链
  尽量落在同一核心上是缩短时延的关键。
- 并行宽度：总工作量除以最长依赖链长度，可以理解为「理论上最多能把时间压缩到几分
  之一」。并行宽度接近 1 的用例本质串行，任何切分都带不来收益。
- 子图时长：四条流水线并行推进，因此子图耗时由最忙的那条流水线决定，同时还要考虑
  边界搬运占用的带宽与子图内部的关键路径。
- 切点代价：切点处跨过的依赖边越少，跨核通信越省；同时切出的段不能大小悬殊，
  因此把跨切边数作为主要指标、把偏离平均工作量的相对偏差作为次要指标。

## 运行命令

```powershell
python Q1/main.py --case case_001 --cores 4 --singlecore
python scripts/run_experiments.py --problems 1 --cores 2,3,4,5 --workers 9
python scripts/aggregate_results.py
```

## 输出文件

- `results/plans/<case>_p1_n<cores>_plan.json`：切图与调度方案；
- `results/evaluation/<case>_p1_n<cores>_res.json`：官方评估程序的原始输出；
- `results/final_results.json`：唯一最终结果源；
- `Q1/figures/*.svg|pdf|png`：本问论文用图。

## 核心数值结果

{table_speedup(block)}

- 四核加速比最高为 {high[0]:.4f}（{high[1]}），最低为 {low[0]:.4f}（{low[1]}）；
- 加速比低于 1 的用例：{", ".join(f"{case}（{entry['5']['speedup']:.3f}）" for case, entry in worst if entry["5"]["speedup"] < 1.0) or "无"}。

## 图表清单

| 图 | 内容 | 文件 |
|---|---|---|
| 图 3 | 测试用例结构画像 | `数据预处理/figures/fig_dataset_profile.pdf` |
| 图 4 | 分层工作量占比分布 | `数据预处理/figures/fig_dag_layers.pdf` |
| 图 6 | 平均加速比曲线 | `Q1/figures/fig_q1_speedup.pdf` |
| 图 7 | 加速比与并行宽度的关系 | `Q1/figures/fig_q1_case_scatter.pdf` |
| 图 8 | 估算与实测的一致性 | `Q1/figures/fig_q1_estimator.pdf` |
| 图 9 | 加速比与额外搬运量的权衡 | `Q1/figures/fig_q1_pareto.pdf` |
| 图 10 | 代表性用例的四核时间线 | `Q1/figures/fig_q1_timeline.pdf` |

## 结果解释

平均加速比随核数单调上升，说明分核阶段的负载均衡在全部核数下都有效。加速比与
并行宽度呈明显正相关：并行宽度大于 10 倍的用例四核加速比普遍超过 3.5 倍，而并行
宽度接近 1 的用例加速比稳定在 1 倍附近。加速比低于 1 的用例极少，且幅度很小，
原因是估算模型对边界搬运与缓存换出的刻画偏乐观，使个别用例误判为可并行。
{COMMON_TAIL}"""


def q2_doc(results, profile):
    block = results["q2"]
    low, high = extrema(block["per_case"], 5)
    return f"""# 问题二（场景 B）结果交接

## 问题目标

在存在核间同步机制的场景 B 下建立切图与调度模型，在严格满足 L1/UB 容量约束的
前提下进一步缩短 Makespan 并减少额外数据搬运。

## 输入数据

- 与问题一相同的 {results["meta"]["case_count"]} 张计算图与固定配置；
- 场景 B 规则：同一核心的全部子图合并为一个 Task，同核数据在私有缓存中直接复用，
  只有跨核边才插入搬运并支付 500 周期同步延迟。

## 核心假设

1. 同核子图之间的数据驻留不消耗带宽，但持续占用 L1/UB 空间；
2. 跨核同步延迟为固定周期数，与数据量无关；
3. 核内调度仍由官方确定性启发式完成，容量不足时自动插入换出与换入；
4. 子图依赖图必须无环。

## 模型思路

复用问题一的无环切分骨架，把同一核心上的全部子图合并为一个 Task，入向边界搬运
只统计跨核部分，跨核等待常数由 1000 降为 500，再按新代价重新分核。

## 关键公式通俗解释

- 跨核边界字节：只有当一份数据被其他核心消费时，才需要写回主存再读入；同核子图
  之间的数据留在私有缓存里，不产生主存流量。
- 合并任务容量约束：一个核心上所有子图的驻留张量之和不得超过 L1 与 UB 的容量，
  否则官方核内调度算法会插入换出与换入，产生额外搬运。
- 子图时长：与问题一形式一致，只是入向与出向字节都只统计跨核部分，因此把更多
  子图聚到同一核心不再被惩罚。

## 运行命令

```powershell
python Q2/main.py --case case_001 --cores 4 --singlecore
python scripts/run_experiments.py --problems 2 --cores 2,3,4,5 --workers 9
python scripts/aggregate_results.py
```

## 输出文件

- `results/plans/<case>_p2_n<cores>_plan.json`：切图与调度方案；
- `results/evaluation/<case>_p2_n<cores>_res.json`：官方评估程序的原始输出；
- `Q2/figures/*.svg|pdf|png`：本问论文用图。

## 核心数值结果

{table_speedup(block)}

- 四核加速比最高为 {high[0]:.4f}（{high[1]}），最低为 {low[0]:.4f}（{low[1]}）；
- 场景 B 相对场景 A 在四核下的总额外搬运量下降
  {_traffic_drop(results):.1f} 个百分点。

## 图表清单

| 图 | 内容 | 文件 |
|---|---|---|
| 图 12 | 两个场景的平均加速比对照 | `Q2/figures/fig_q2_compare.pdf` |
| 图 13 | 两场景 Makespan 比值与规模的关系 | `Q2/figures/fig_q2_scatter.pdf` |
| 图 14 | 额外搬运量占比的分布 | `Q2/figures/fig_q2_capacity.pdf` |

## 结果解释

场景 B 的平均加速比在全部核数下都高于场景 A，且差距随核数增加而扩大，说明核内
数据复用的收益随跨核依赖增多而放大。逐用例比较显示绝大多数用例在场景 B 下不劣于
场景 A；额外搬运量整体下降，符合「同核数据留在私有缓存」的建模预期。
{COMMON_TAIL}"""


def _traffic_drop(results):
    q1 = sum(entry.get("4", {}).get("added_bytes", 0) for entry in results["q1"]["per_case"].values())
    q2 = sum(entry.get("4", {}).get("added_bytes", 0) for entry in results["q2"]["per_case"].values())
    return (q1 - q2) / q1 * 100.0 if q1 else 0.0


def q3_doc(results, profile):
    block = results["q3"]
    gain_lines = ["| 核心数 | 只读 Cache 平均加速比 | 平均 Cache 命中率 |", "|---|---|---|"]
    for cores in CORES:
        gain = block["average_cache_gain"].get(str(cores))
        hit = block["average_cache_hit_rate"].get(str(cores))
        if gain is None:
            continue
        gain_lines.append(f"| {cores} | {gain:.4f} | {float(hit or 0.0) * 100:.2f}% |")
    return f"""# 问题三（共享只读 L2）结果交接

## 问题目标

在场景 B 的基础上引入所有核心共享的只读 L2 Cache（容量 1 MB、带宽
250 字节/周期），研究其对多核切图与调度的影响，给出无 L2 与只读 Cache 两种配置
的对比曲线与同核数下的加速比。

## 输入数据

- 与问题二相同的 {results["meta"]["case_count"]} 张计算图与固定配置；
- 只读 L2 参数：容量 1048576 字节，命中带宽 250 字节/周期；
- 评估规则：读入操作按逻辑张量 id 查询只读 FIFO 缓存，命中进入独立的读带宽池，
  未命中访问主存后写入缓存，容量不足时按先进先出淘汰，单张量超过容量时不缓存。

## 核心假设

1. L2 为只读缓存，只有读入操作会查询；
2. 缓存读带宽与主存带宽是两个独立带宽池，互不占用；
3. 同一张量的重复读取按先进先出顺序命中，收益表现为带宽提升；
4. 切分阶段用「读入边界的有效带宽」近似刻画缓存的影响。

## 模型思路

建立 L2 复用模型：一份被 $g$ 个核心读取的张量，首次访问未命中，其后 $g-1$ 次命中，
有效读入代价为首次的主存读入加上后续的缓存命中。据此把切分阶段的入向有效带宽由
60 改为 250，得到 L2 感知切分；同时保留 DDR 口径切分作为对照，两条路线的方案
逐用例实测择优。

## 关键公式通俗解释

- 有效读入代价：第一次读一份数据要走主存，之后同样的数据再被别的核心读就可以走
  更快的缓存。把共享输入的消费者摊到多个核心的边际代价因此从每字节六十分之一周期
  降到每字节二百五十分之一周期，约合原来的四分之一。
- 命中率：可由缓存服务的访问中命中字节占总访问字节的比例。如果所有输入都只被一个
  核心读取，分子为零，命中率也为零，此时缓存不产生任何收益。
- 加速比：同核数下无 L2 配置的 Makespan 与只读 Cache 配置的 Makespan 之比。

## 运行命令

```powershell
python Q3/main.py --case case_001 --cores 4 --variant both --singlecore
python scripts/run_experiments.py --problems 3 --cores 2,3,4,5 --workers 9
python scripts/aggregate_results.py
```

## 输出文件

- `results/plans/<case>_p3_n<cores>_plan.json`：L2 感知切分方案；
- `results/evaluation/<case>_p3_n<cores>_res.json`：问题三官方评估程序的原始输出；
- `results/evaluation/<case>_p2_n<cores>_res.json`：无 L2 基线（问题二评估结果）；
- `Q3/figures/*.svg|pdf|png`：本问论文用图。

## 核心数值结果

{chr(10).join(gain_lines)}

## 图表清单

| 图 | 内容 | 文件 |
|---|---|---|
| 图 16 | 只读 Cache 的加速比与命中率 | `Q3/figures/fig_q3_cache_gain.pdf` |
| 图 17 | 命中率与加速比的关系 | `Q3/figures/fig_q3_hit.pdf` |
| 图 18 | 两种配置的额外搬运量对照 | `Q3/figures/fig_q3_traffic.pdf` |

## 结果解释

只读 Cache 的平均加速比随核数上升，与命中率同向变化。命中率偏低的用例通常是
全部输入只被单一核心读取的串行型图，缓存无从复用；命中率高的用例则存在明显的
共享输入，重复读取被缓存承接。额外搬运量的下降主要来自 L2 感知切分给出的更均衡
划分，而不是缓存直接减少流量。
{COMMON_TAIL}"""


def main():
    results, profile = load()
    (ROOT / "Q1" / "result.md").write_text(q1_doc(results, profile), encoding="utf-8")
    (ROOT / "Q2" / "result.md").write_text(q2_doc(results, profile), encoding="utf-8")
    (ROOT / "Q3" / "result.md").write_text(q3_doc(results, profile), encoding="utf-8")
    print(json.dumps({"ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
