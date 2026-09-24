from __future__ import annotations
import math
from collections import defaultdict, deque
from graph_utils import build_op_dag, contract_copy, op_cost, topological
BANDWIDTH = 60.0

class GraphIndex:

    def __init__(self, graph):
        self.graph = graph
        self.op_by_id, preds, succs, self.eligible = build_op_dag(graph)
        self.cpreds, self.csuccs = contract_copy(preds, succs, self.eligible)
        self.order = topological(self.eligible, self.cpreds, self.csuccs)
        self.order_pos = {node: pos for pos, node in enumerate(self.order)}
        self.tensor_size = {t['id']: int(t['size']) for t in graph['tensors']}
        self.is_ddr = {t['id']: t['pos'] == 'DDR' for t in graph['tensors']}
        self.ddr_bytes = sum((t['size'] for t in graph['tensors'] if t['pos'] == 'DDR'))
        op_ids = {op['id'] for op in graph['ops']}
        producers = defaultdict(set)
        consumers = defaultdict(set)
        for edge in graph['edges']:
            src, dst = (edge['source'], edge['target'])
            if src in op_ids and dst not in op_ids:
                producers[dst].add(src)
            elif src not in op_ids and dst in op_ids:
                consumers[src].add(dst)
        self.in_tensors = defaultdict(list)
        self.out_tensors = defaultdict(list)
        self.graph_output_tensors = set()
        for tensor_id, consumers_of in consumers.items():
            for consumer in consumers_of:
                if consumer in self.eligible:
                    self.in_tensors[consumer].append(tensor_id)
            if any((c not in self.eligible for c in consumers_of)):
                self.graph_output_tensors.add(tensor_id)
        for tensor_id, producers_of in producers.items():
            for producer in producers_of:
                if producer in self.eligible:
                    self.out_tensors[producer].append(tensor_id)
        self.tensor_consumers = {tensor_id: sorted((c for c in consumers_of if c in self.eligible)) for tensor_id, consumers_of in consumers.items()}
        self.cm = {}
        self.cv = {}
        for node in self.eligible:
            op = self.op_by_id[node]
            cycles = op_cost(op)
            self.cm[node] = cycles if op['pipe'] == 'PIPE_M' else 0
            self.cv[node] = cycles if op['pipe'] == 'PIPE_V' else 0
        self.weight = {n: float(self.cm[n] + self.cv[n]) for n in self.eligible}

    def downstream_weight(self):
        down = dict(self.weight)
        for node in reversed(self.order):
            total = self.weight[node]
            for succ in self.csuccs[node]:
                total += down.get(succ, 0.0)
            down[node] = total
        return down

class PartitionState:

    def __init__(self, index: GraphIndex, num_cores: int, in_bandwidth: float=BANDWIDTH):
        self.index = index
        self.num_cores = num_cores
        self.in_bandwidth = in_bandwidth
        self.core_of = {}
        self.subgraph_of = {}
        self.subgraph_core = {}
        self.m_sum = [0.0] * num_cores
        self.v_sum = [0.0] * num_cores
        self.in_bytes = [0.0] * num_cores
        self.out_bytes = [0.0] * num_cores
        self.cons_groups = defaultdict(lambda: defaultdict(int))
        self.prod_groups = defaultdict(lambda: defaultdict(int))
        self.cross = defaultdict(int)

    def _tensor_contribs(self, tensor_id):
        size = self.index.tensor_size[tensor_id]
        cons = self.cons_groups.get(tensor_id) or {}
        prod = self.prod_groups.get(tensor_id) or {}
        in_contrib = {}
        for group, count in cons.items():
            if group not in prod:
                in_contrib[group] = size * count
        out_contrib = {}
        is_output = tensor_id in self.index.graph_output_tensors
        if prod:
            for group, count in prod.items():
                others = sum((c for g, c in cons.items() if g != group))
                if others > 0 or is_output:
                    out_contrib[group] = size * count
        return (in_contrib, out_contrib)

    def _update_tensor(self, tensor_id, core, delta, consume):
        before_in, before_out = self._tensor_contribs(tensor_id)
        table = self.cons_groups if consume else self.prod_groups
        entry = table[tensor_id]
        entry[core] += delta
        if entry[core] <= 0:
            del entry[core]
        after_in, after_out = self._tensor_contribs(tensor_id)
        for group, value in before_in.items():
            self.in_bytes[group] -= value
        for group, value in after_in.items():
            self.in_bytes[group] += value
        for group, value in before_out.items():
            self.out_bytes[group] -= value
        for group, value in after_out.items():
            self.out_bytes[group] += value

    def add(self, node, core, subgraph=None):
        index = self.index
        self.core_of[node] = core
        subgraph = core if subgraph is None else subgraph
        self.subgraph_of[node] = subgraph
        self.subgraph_core[subgraph] = core
        self.m_sum[core] += index.cm[node]
        self.v_sum[core] += index.cv[node]
        for tensor_id in index.in_tensors[node]:
            self._update_tensor(tensor_id, core, +1, consume=True)
        for tensor_id in index.out_tensors[node]:
            self._update_tensor(tensor_id, core, +1, consume=False)
        for pre in index.cpreds[node]:
            other = self.core_of.get(pre)
            if other is not None and other != core:
                self.cross[other, core] += 1
        for succ in index.csuccs[node]:
            other = self.core_of.get(succ)
            if other is not None and other != core:
                self.cross[core, other] += 1

    def move(self, node, new_core):
        old = self.core_of[node]
        if old == new_core:
            return
        index = self.index
        self.core_of[node] = new_core
        self.m_sum[old] -= index.cm[node]
        self.m_sum[new_core] += index.cm[node]
        self.v_sum[old] -= index.cv[node]
        self.v_sum[new_core] += index.cv[node]
        for tensor_id in index.in_tensors[node]:
            self._update_tensor(tensor_id, old, -1, consume=True)
            self._update_tensor(tensor_id, new_core, +1, consume=True)
        for tensor_id in index.out_tensors[node]:
            self._update_tensor(tensor_id, old, -1, consume=False)
            self._update_tensor(tensor_id, new_core, +1, consume=False)
        for pre in index.cpreds[node]:
            other = self.core_of.get(pre)
            if other is None:
                continue
            if other != old:
                self.cross[other, old] -= 1
            if other != new_core:
                self.cross[other, new_core] += 1
        for succ in index.csuccs[node]:
            other = self.core_of.get(succ)
            if other is None:
                continue
            if other != old:
                self.cross[old, other] -= 1
            if other != new_core:
                self.cross[new_core, other] += 1

    def durations(self):
        result = []
        for core in range(self.num_cores):
            result.append(max(self.m_sum[core], self.v_sum[core], self.in_bytes[core] / self.in_bandwidth, self.out_bytes[core] / BANDWIDTH))
        return result

    def quotient(self):
        preds = defaultdict(set)
        for (src, dst), count in self.cross.items():
            if count > 0:
                preds[dst].add(src)
        return preds

    def acyclic(self):
        preds = self.quotient()
        indeg = {c: len(preds[c]) for c in range(self.num_cores)}
        ready = deque(sorted((c for c in range(self.num_cores) if indeg[c] == 0)))
        seen = 0
        while ready:
            core = ready.popleft()
            seen += 1
            for other in range(self.num_cores):
                if core in preds[other]:
                    indeg[other] -= 1
                    if indeg[other] == 0:
                        ready.append(other)
        return seen == self.num_cores

    def objective(self, cross_wait):
        preds = self.quotient()
        durations = self.durations()
        indeg = {c: len(preds[c]) for c in range(self.num_cores)}
        ready = deque(sorted((c for c in range(self.num_cores) if indeg[c] == 0)))
        order = []
        while ready:
            core = ready.popleft()
            order.append(core)
            for other in range(self.num_cores):
                if core in preds[other]:
                    indeg[other] -= 1
                    if indeg[other] == 0:
                        ready.append(other)
        if len(order) < self.num_cores:
            return (float('inf'), durations)
        finish = {}
        for core in order:
            start = 0.0
            for pre in preds[core]:
                start = max(start, finish[pre] + cross_wait)
            finish[core] = start + durations[core]
        return (max(finish.values()), durations)

    def task_graph(self):
        deps = defaultdict(set)
        for node in self.index.order:
            src = self.subgraph_of.get(node)
            if src is None:
                continue
            for succ in self.index.csuccs[node]:
                dst = self.subgraph_of.get(succ)
                if dst is not None and dst != src:
                    deps[src].add(dst)
        return deps

    def task_acyclic(self):
        deps = self.task_graph()
        preds = defaultdict(set)
        for src, targets in deps.items():
            for dst in targets:
                preds[dst].add(src)
        nodes = set(self.subgraph_of.values())
        indeg = {n: len(preds[n]) for n in nodes}
        ready = deque(sorted((n for n in nodes if indeg[n] == 0)))
        seen = 0
        while ready:
            node = ready.popleft()
            seen += 1
            for dst in deps.get(node, ()):
                indeg[dst] -= 1
                if indeg[dst] == 0:
                    ready.append(dst)
        return seen == len(nodes)

    def subgraph_durations(self):
        index = self.index
        members = defaultdict(list)
        m_sum = defaultdict(float)
        v_sum = defaultdict(float)
        for node, subgraph in self.subgraph_of.items():
            members[subgraph].append(node)
            m_sum[subgraph] += index.cm[node]
            v_sum[subgraph] += index.cv[node]
        best = {}
        critical = defaultdict(float)
        for node in index.order:
            subgraph = self.subgraph_of[node]
            weight = index.cm[node] + index.cv[node]
            parent = 0
            for pre in index.cpreds[node]:
                if self.subgraph_of.get(pre) == subgraph and best.get(pre, 0) > parent:
                    parent = best[pre]
            best[node] = parent + weight
            if best[node] > critical[subgraph]:
                critical[subgraph] = best[node]
        in_bytes, out_bytes = self._boundary_bytes()
        durations = {}
        for subgraph in members:
            durations[subgraph] = max(m_sum[subgraph], v_sum[subgraph], in_bytes.get(subgraph, 0) / self.in_bandwidth, out_bytes.get(subgraph, 0) / BANDWIDTH, critical[subgraph])
        return durations

    def _boundary_bytes(self):
        in_bytes = defaultdict(float)
        out_bytes = defaultdict(float)
        index = self.index
        seen_in = set()
        for node, subgraph in self.subgraph_of.items():
            for tensor_id in index.in_tensors[node]:
                key = (subgraph, tensor_id)
                if key in seen_in:
                    continue
                seen_in.add(key)
                consumers = index.tensor_consumers.get(tensor_id, ())
                targets = {self.subgraph_of.get(c) for c in consumers} - {None}
                if index.is_ddr[tensor_id] or len(targets - {subgraph}) > 0:
                    in_bytes[subgraph] += index.tensor_size[tensor_id]
        seen_out = set()
        for node, subgraph in self.subgraph_of.items():
            for tensor_id in index.out_tensors[node]:
                key = (subgraph, tensor_id)
                if key in seen_out:
                    continue
                seen_out.add(key)
                consumers = index.tensor_consumers.get(tensor_id, ())
                targets = {self.subgraph_of.get(c) for c in consumers} - {None}
                if tensor_id in index.graph_output_tensors or len(targets - {subgraph}) > 0:
                    out_bytes[subgraph] += index.tensor_size[tensor_id]
        return (in_bytes, out_bytes)

    def task_objective(self, cross_wait, same_core_wait=100.0):
        if not self.task_acyclic():
            return float('inf')
        durations = self.subgraph_durations()
        deps = self.task_graph()
        preds = defaultdict(set)
        succs = defaultdict(set)
        for src, targets in deps.items():
            for dst in targets:
                preds[dst].add(src)
                succs[src].add(dst)
        nodes = sorted(set(self.subgraph_of.values()))
        indeg = {n: len(preds[n]) for n in nodes}
        ready = deque(sorted((n for n in nodes if indeg[n] == 0)))
        order = []
        while ready:
            node = ready.popleft()
            order.append(node)
            for dst in sorted(succs.get(node, ())):
                indeg[dst] -= 1
                if indeg[dst] == 0:
                    ready.append(dst)
        if len(order) < len(nodes):
            return float('inf')
        on_core = defaultdict(list)
        for subgraph in order:
            on_core[self.subgraph_core[subgraph]].append(subgraph)
        finish = {}
        core_free = {core: 0.0 for core in range(self.num_cores)}
        for subgraph in order:
            core = self.subgraph_core[subgraph]
            start = core_free[core]
            for pre in preds[subgraph]:
                penalty = 0.0 if self.subgraph_core[pre] == core else cross_wait
                start = max(start, finish[pre] + penalty)
            finish[subgraph] = start + durations[subgraph]
            core_free[core] = finish[subgraph]
        makespan = max(finish.values()) if finish else 0.0
        in_bytes, out_bytes = self._boundary_bytes()
        total_ddr = self.index.ddr_bytes + sum(in_bytes.values()) + sum(out_bytes.values())
        return max(makespan, total_ddr / BANDWIDTH)

    def _core_of_subgraph(self, subgraph):
        for node, value in self.subgraph_of.items():
            if value == subgraph:
                return self.core_of[node]
        return None

def initial_assignment(index: GraphIndex, num_cores: int, in_bandwidth: float=BANDWIDTH):
    down = index.downstream_weight()
    primary = {}
    for node in index.order:
        preds = index.cpreds[node]
        if not preds:
            continue
        primary[node] = max(preds, key=lambda p: (down.get(p, 0.0), -p))
    state = PartitionState(index, num_cores, in_bandwidth=in_bandwidth)
    source_load = [0.0] * num_cores
    for node in index.order:
        if node not in primary:
            core = min(range(num_cores), key=lambda c: (source_load[c], c))
            source_load[core] += index.weight[node]
            state.add(node, core)
        else:
            state.add(node, state.core_of[primary[node]])
    return state

def break_cycles(state: PartitionState, rounds=40):
    index = state.index
    down = index.downstream_weight()
    for _ in range(rounds):
        if state.acyclic():
            return True
        preds = state.quotient()
        cycle = _find_cycle(preds, state.num_cores)
        if not cycle:
            return state.acyclic()
        a, b = (cycle[0], cycle[1])
        candidates = [node for node, core in state.core_of.items() if core == b and any((state.core_of.get(p) == a for p in index.cpreds[node]))]
        if not candidates:
            return state.acyclic()
        node = min(candidates, key=lambda n: index.weight[n])
        state.move(node, a)
    return state.acyclic()

def _find_cycle(preds, num_cores):
    color = {}
    for start in range(num_cores):
        if color.get(start):
            continue
        stack = [(start, iter(sorted(preds[start])))]
        path = [start]
        color[start] = 1
        while stack:
            node, iterator = stack[-1]
            advanced = False
            for nxt in iterator:
                if color.get(nxt) == 1:
                    index = path.index(nxt)
                    return path[index:] + [nxt]
                if not color.get(nxt):
                    color[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, iter(sorted(preds[nxt]))))
                    advanced = True
                    break
            if not advanced:
                color[node] = 2
                stack.pop()
                path.pop()
    return None

def local_search(state: PartitionState, cross_wait, rounds=10, budget=4000):
    index = state.index
    best, durations = state.objective(cross_wait)
    if not math.isfinite(best):
        return best
    evaluations = 0
    for _ in range(rounds):
        durations = state.durations()
        hot = max(range(state.num_cores), key=lambda c: durations[c])
        members = [n for n, c in state.core_of.items() if c == hot]
        members.sort(key=lambda n: -index.weight[n])
        limit = max(64, int(len(members) / 2))
        improved = False
        for node in members[:limit]:
            if evaluations >= budget:
                return best
            origin = state.core_of[node]
            for target in range(state.num_cores):
                if target == origin:
                    continue
                state.move(node, target)
                evaluations += 1
                if state.acyclic():
                    score, _ = state.objective(cross_wait)
                    if score < best - 1e-09:
                        best = score
                        improved = True
                        break
                state.move(node, origin)
            if improved:
                break
        if not improved:
            break
    return best

def monotone_assignment(index: GraphIndex, num_cores: int, in_bandwidth: float=BANDWIDTH):
    state = PartitionState(index, num_cores, in_bandwidth=in_bandwidth)
    for node in index.order:
        preds = [state.core_of[p] for p in index.cpreds[node] if p in state.core_of]
        lower = max(preds) if preds else 0
        core = min(range(lower, num_cores), key=lambda c: (state.m_sum[c] + state.v_sum[c], c))
        state.add(node, core)
    return state

def _block_bounds(index: GraphIndex, sequence, num_cores):
    total = sum((index.weight[n] for n in sequence))
    target = total / num_cores
    position = {node: pos for pos, node in enumerate(sequence)}
    crossing = [0] * (len(sequence) + 1)
    for node in sequence:
        pos = position[node]
        for succ in index.csuccs[node]:
            other = position[succ]
            if other > pos:
                crossing[pos + 1] += 1
    prefix = [0.0]
    for node in sequence:
        prefix.append(prefix[-1] + index.weight[node])
    bounds = [0]
    start = 0
    for block in range(num_cores - 1):
        remaining = num_cores - block - 1
        low, high = (target * 0.7, target * 1.35)
        best_pos, best_key, fallback, fallback_gap = (None, None, None, None)
        for pos in range(start + 1, len(sequence) - remaining + 1):
            weight = prefix[pos] - prefix[start]
            gap = abs(weight - target)
            if fallback_gap is None or gap < fallback_gap:
                fallback_gap, fallback = (gap, pos)
            if not low <= weight <= high:
                continue
            if remaining and total - prefix[pos] < remaining * low:
                continue
            key = (crossing[pos], gap)
            if best_key is None or key < best_key:
                best_key, best_pos = (key, pos)
        bounds.append(best_pos if best_pos is not None else fallback)
        start = bounds[-1]
    bounds.append(len(sequence))
    return bounds

def _block_state(index: GraphIndex, sequence, bounds, num_cores, cross_wait, in_bandwidth: float=BANDWIDTH):
    stats = []
    block_of = {}
    for block in range(num_cores):
        members = sequence[bounds[block]:bounds[block + 1]]
        for node in members:
            block_of[node] = block
        member_set = set(members)
        m_sum = sum((index.cm[n] for n in members))
        v_sum = sum((index.cv[n] for n in members))
        in_bytes = 0
        out_bytes = 0
        seen = set()
        for node in members:
            for tensor_id in index.in_tensors[node]:
                if tensor_id in seen:
                    continue
                seen.add(tensor_id)
                consumers = index.tensor_consumers.get(tensor_id, ())
                if index.is_ddr[tensor_id] or any((c not in member_set for c in consumers)):
                    in_bytes += index.tensor_size[tensor_id]
            for tensor_id in index.out_tensors[node]:
                if tensor_id in seen:
                    continue
                seen.add(tensor_id)
                consumers = index.tensor_consumers.get(tensor_id, ())
                if tensor_id in index.graph_output_tensors or any((c not in member_set for c in consumers)):
                    out_bytes += index.tensor_size[tensor_id]
        stats.append(max(m_sum, v_sum, in_bytes / BANDWIDTH, out_bytes / BANDWIDTH))
    deps = set()
    for node in sequence:
        for succ in index.csuccs[node]:
            if block_of[succ] != block_of[node]:
                deps.add((block_of[node], block_of[succ]))
    succs = defaultdict(set)
    preds = defaultdict(set)
    for src, dst in deps:
        succs[src].add(dst)
        preds[dst].add(src)
    bottom = dict(enumerate(stats))
    for block in reversed(range(num_cores)):
        for succ in succs[block]:
            bottom[block] = max(bottom[block], stats[block] + bottom[succ])
    ready = sorted((b for b in range(num_cores) if not preds[b]), key=lambda b: (-bottom[b], b))
    core_free = [0.0] * num_cores
    core_of_block = {}
    finish = {}
    placed = 0
    while placed < num_cores:
        if not ready:
            waiting = sorted((b for b in range(num_cores) if b not in finish), key=lambda b: (-bottom[b], b))
            ready.append(waiting[0])
        block = ready.pop(0)
        best_core, best_finish = (None, None)
        for core in range(num_cores):
            start = core_free[core]
            for pre in preds[block]:
                if pre in finish:
                    penalty = 0.0 if core_of_block[pre] == core else cross_wait
                    start = max(start, finish[pre] + penalty)
            end = start + stats[block]
            if best_finish is None or end < best_finish - 1e-09:
                best_finish, best_core = (end, core)
        core_of_block[block] = best_core
        core_free[best_core] = best_finish
        finish[block] = best_finish
        placed += 1
        for succ in sorted(succs[block]):
            preds[succ].discard(block)
            if not preds[succ]:
                ready.append(succ)
        ready.sort(key=lambda b: (-bottom[b], b))
    state = PartitionState(index, num_cores, in_bandwidth=in_bandwidth)
    for node in sequence:
        state.add(node, core_of_block[block_of[node]])
    return (state, max(finish.values()) if finish else 0.0)

def block_assignment(index: GraphIndex, num_cores: int, cross_wait: float, in_bandwidth: float=BANDWIDTH):
    sequence = _descendant_order(index)
    bounds = _block_bounds(index, sequence, num_cores)
    state, _ = _block_state(index, sequence, bounds, num_cores, cross_wait, in_bandwidth)
    return state

def cross_edge_count(state: PartitionState):
    return sum((count for count in state.cross.values() if count > 0))

def refine(state: PartitionState, rounds=6, budget=6000):
    index = state.index
    evaluations = 0
    for _ in range(rounds):
        improved = False
        boundary = sorted({node for (src, dst), count in state.cross.items() if count > 0 for node in ()})
        boundary = [n for n, c in state.core_of.items() if _node_on_cut(state, n)]
        boundary.sort(key=lambda n: -index.weight[n])
        for node in boundary:
            if evaluations >= budget:
                return
            origin = state.core_of[node]
            base = _refine_score(state)
            for target in range(state.num_cores):
                if target == origin:
                    continue
                state.move(node, target)
                evaluations += 1
                if _refine_score(state) < base - 1e-09:
                    improved = True
                    break
                state.move(node, origin)
        if not improved:
            break

def _node_on_cut(state: PartitionState, node):
    index = state.index
    core = state.core_of[node]
    for other in index.cpreds[node]:
        if state.core_of.get(other, core) != core:
            return True
    for other in index.csuccs[node]:
        if state.core_of.get(other, core) != core:
            return True
    return False

def _refine_score(state: PartitionState):
    durations = state.durations()
    return max(durations) + 0.5 * cross_edge_count(state)

def repair_cycles(state: PartitionState, rounds=200):
    index = state.index
    for _ in range(rounds):
        if state.acyclic():
            return True
        preds = state.quotient()
        cycle = _find_cycle(preds, state.num_cores)
        if not cycle:
            return state.acyclic()
        pair = None
        for i in range(len(cycle) - 1):
            a, b = (cycle[i], cycle[i + 1])
            candidates = [node for node, core in state.core_of.items() if core == b and any((state.core_of.get(p) == a for p in index.cpreds[node]))]
            if candidates:
                pair = (a, candidates)
                break
        if pair is None:
            return state.acyclic()
        target, candidates = pair
        node = min(candidates, key=lambda n: (index.weight[n], n))
        state.move(node, target)
    return state.acyclic()

def critical_path_of(index: GraphIndex, core_of, core):
    best = {}
    for node in index.order:
        if core_of[node] != core:
            continue
        weight = index.cm[node] + index.cv[node]
        parent = 0
        for pre in index.cpreds[node]:
            if pre in best and best[pre] > parent:
                parent = best[pre]
        best[node] = parent + weight
    return max(best.values()) if best else 0

def single_core_state(index: GraphIndex, num_cores: int, in_bandwidth: float=BANDWIDTH):
    state = PartitionState(index, num_cores, in_bandwidth=in_bandwidth)
    for node in index.order:
        state.add(node, 0)
    return state

def level_assignment(index: GraphIndex, num_cores: int, band=1, balance_blocks=None, in_bandwidth: float=BANDWIDTH):
    level = {}
    for node in index.order:
        best = 0
        for pre in index.cpreds[node]:
            if pre in level and level[pre] + 1 > best:
                best = level[pre] + 1
        level[node] = best
    bands = defaultdict(list)
    for node in index.order:
        bands[int(level[node] / max(1, band))].append(node)
    blocks_per_band = balance_blocks or num_cores
    state = PartitionState(index, num_cores, in_bandwidth=in_bandwidth)
    load = [0.0] * num_cores
    next_subgraph = 0
    for key in sorted(bands):
        members = bands[key]
        total = sum((index.weight[n] for n in members))
        target = total / blocks_per_band if blocks_per_band else total
        blocks = []
        current, accumulated = ([], 0.0)
        for node in members:
            current.append(node)
            accumulated += index.weight[node]
            if accumulated >= target and len(blocks) < blocks_per_band - 1:
                blocks.append(current)
                current, accumulated = ([], 0.0)
        if current:
            blocks.append(current)
        for block in blocks:
            weight = sum((index.weight[n] for n in block))
            core = min(range(num_cores), key=lambda c: (load[c], c))
            for node in block:
                state.add(node, core, next_subgraph)
            load[core] += weight
            next_subgraph += 1
    return state

def build_plan(graph, num_cores, cross_wait=1000.0, same_core_wait=100.0, in_bandwidth=BANDWIDTH, search_rounds=8, search_budget=3000, refine_rounds=3, refine_budget=2500, level_bands=(1, 2, 4), safety_margin=0.85):
    index = GraphIndex(graph)
    candidates = []
    cone = initial_assignment(index, num_cores, in_bandwidth)
    refine(cone, rounds=refine_rounds, budget=refine_budget)
    if repair_cycles(cone):
        candidates.append(cone)
    monotone = monotone_assignment(index, num_cores, in_bandwidth)
    if monotone.acyclic():
        candidates.append(monotone)
    blocks = block_assignment(index, num_cores, cross_wait, in_bandwidth)
    if blocks.acyclic():
        candidates.append(blocks)
    for band in level_bands:
        layered = level_assignment(index, num_cores, band=band, in_bandwidth=in_bandwidth)
        if layered.task_acyclic():
            candidates.append(layered)
    if not candidates:
        candidates.append(_fallback_assignment(index, num_cores, in_bandwidth))

    def key(candidate):
        score = candidate.task_objective(cross_wait, same_core_wait)
        return (not candidate.task_acyclic(), score, len(candidate.subgraph_core))
    state = min(candidates, key=key)
    if num_cores > 1:
        single = single_core_state(index, num_cores, in_bandwidth)
        single_est = max(single.durations()[0], float(critical_path_of(index, single.core_of, 0)))
        chosen_est = state.task_objective(cross_wait, same_core_wait)
        if chosen_est > single_est * safety_margin:
            state = single
    core_of = dict(state.core_of)
    node_to_subgraph = dict(state.subgraph_of)
    groups = defaultdict(list)
    for node, subgraph in node_to_subgraph.items():
        groups[subgraph].append(node)
    first_pos = {s: min((index.order_pos[n] for n in members)) for s, members in groups.items()}
    per_core = defaultdict(list)
    for subgraph, members in groups.items():
        per_core[core_of[members[0]]].append(subgraph)
    core_schedules = [sorted(per_core.get(core, []), key=lambda s: first_pos[s]) for core in range(num_cores)]
    return {'node_to_subgraph': {str(n): int(s) for n, s in sorted(node_to_subgraph.items())}, 'core_schedules': core_schedules}

def _fallback_assignment(index: GraphIndex, num_cores: int, in_bandwidth: float=BANDWIDTH):
    sequence = _descendant_order(index)
    total = sum((index.weight[n] for n in sequence))
    target = total / num_cores
    state = PartitionState(index, num_cores, in_bandwidth=in_bandwidth)
    prefix = 0.0
    core = 0
    for position, node in enumerate(sequence):
        state.add(node, core)
        prefix += index.weight[node]
        remaining_nodes = len(sequence) - position - 1
        remaining_cores = num_cores - core - 1
        if core < num_cores - 1 and prefix >= target * (core + 1) and (remaining_nodes > remaining_cores):
            core += 1
    return state

def _descendant_order(index: GraphIndex):
    down = index.downstream_weight()
    roots = [n for n in index.order if not index.cpreds[n]]
    roots.sort(key=lambda n: (-down[n], n))
    visited = set()
    postorder = []
    for root in roots:
        if root in visited:
            continue
        visited.add(root)
        stack = [(root, iter(sorted(index.csuccs[root], key=lambda n: (-down[n], n))))]
        while stack:
            node, iterator = stack[-1]
            advanced = False
            for succ in iterator:
                if succ not in visited:
                    visited.add(succ)
                    stack.append((succ, iter(sorted(index.csuccs[succ], key=lambda n: (-down[n], n)))))
                    advanced = True
                    break
            if not advanced:
                postorder.append(node)
                stack.pop()
    for node in index.order:
        if node not in visited:
            visited.add(node)
            postorder.append(node)
    return list(reversed(postorder))
