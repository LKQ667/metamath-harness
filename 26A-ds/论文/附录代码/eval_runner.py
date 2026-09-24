from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = PROJECT_ROOT / 'results' / 'evaluation'
EVALUATORS = {1: 'multicore_cut_evaluate_problem_1.py', 2: 'multicore_cut_evaluate_problem_2.py', 3: 'multicore_cut_evaluate_problem_3.py'}
_SUITE: Path | None = None

def suite_dir() -> Path:
    global _SUITE
    if _SUITE is not None:
        return _SUITE
    candidates = [PROJECT_ROOT / '赛题' / '_附件解压', PROJECT_ROOT.parent / '_hw_suite']
    env = os.environ.get('HUAWEI_SUITE_DIR')
    if env:
        candidates.insert(0, Path(env))
    for candidate in candidates:
        if (candidate / 'data' / 'config.txt').is_file():
            _SUITE = candidate
            return candidate
    raise FileNotFoundError('未找到赛题附件解压目录，请先解压附件或设置 HUAWEI_SUITE_DIR')

def code_dir() -> Path:
    return suite_dir() / 'code'

def data_dir() -> Path:
    return suite_dir() / 'data'

def config_path() -> Path:
    return data_dir() / 'config.txt'

def all_case_names() -> list[str]:
    return sorted((path.stem for path in data_dir().glob('case_*.json')))

def _env():
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env

def case_path(case_name):
    return data_dir() / f'{case_name}.json'

def _side_paths(result_path):
    result_path = Path(result_path)
    stem = result_path.name[:-len('_res.json')] if result_path.name.endswith('_res.json') else result_path.stem
    return (result_path.with_name(f'{stem}_log.txt'), result_path.with_name(f'{stem}_trace.json'))

def run_evaluator(problem, graph_path, plan_path, result_path=None, keep_trace=False):
    script = code_dir() / EVALUATORS[problem]
    graph_path = Path(graph_path)
    plan_path = Path(plan_path)
    if result_path is None:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        result_path = WORK_DIR / f'{graph_path.stem}_problem_{problem}_res.json'
    result_path = Path(result_path)
    log_path, trace_path = _side_paths(result_path)
    command = [sys.executable, str(script), str(graph_path), str(plan_path), '--config', str(config_path()), '-o', str(result_path), '--log-output', str(log_path), '--trace-output', str(trace_path)]
    proc = subprocess.run(command, cwd=str(suite_dir()), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', env=_env())
    if proc.returncode != 0:
        raise RuntimeError(f'evaluator failed (problem {problem}, {graph_path.name}): {proc.stderr.strip() or proc.stdout.strip()}')
    if not keep_trace:
        trace_path.unlink(missing_ok=True)
    return json.loads(result_path.read_text(encoding='utf-8'))

def run_singlecore(graph_path, result_path=None, keep_trace=False):
    script = code_dir() / 'singlecore_evaluate.py'
    graph_path = Path(graph_path)
    if result_path is None:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        result_path = WORK_DIR / f'{graph_path.stem}_singlecore_res.json'
    result_path = Path(result_path)
    log_path, trace_path = _side_paths(result_path)
    command = [sys.executable, str(script), str(graph_path), '--config', str(config_path()), '-o', str(result_path), '--log-output', str(log_path), '--trace-output', str(trace_path)]
    proc = subprocess.run(command, cwd=str(suite_dir()), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', env=_env())
    if proc.returncode != 0:
        raise RuntimeError(f'singlecore evaluator failed ({graph_path.name}): {proc.stderr.strip() or proc.stdout.strip()}')
    if not keep_trace:
        trace_path.unlink(missing_ok=True)
    return json.loads(result_path.read_text(encoding='utf-8'))

def write_plan(plan, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    return path
