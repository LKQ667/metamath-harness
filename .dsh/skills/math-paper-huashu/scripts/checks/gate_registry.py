#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""math-paper-huashu 阶段门禁的单一注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STAGES = ("step0", "step1", "step2", "step3", "step4", "step5")


@dataclass(frozen=True)
class GateSpec:
    script: str
    first_stage: int
    stage_argument: bool = False
    repeat: bool = True


GATES = (
    GateSpec("check_latex_environment.py", 0, repeat=False),
    GateSpec("check_stage_contract.py", 0, stage_argument=True),
    GateSpec("check_data_sources.py", 0),
    GateSpec("check_no_absolute_paths.py", 0),
    GateSpec("check_no_env_or_cache.py", 0),
    GateSpec("check_result_ranges.py", 3),
    GateSpec("check_code_distribution.py", 3),
    GateSpec("check_figures_manifest.py", 3),
    GateSpec("check_python_figure_contract.py", 3),
    GateSpec("check_python_figure_quality.py", 3),
    GateSpec("check_python_bar_chart_policy.py", 3),
    GateSpec("check_flowchart_required.py", 3),
    GateSpec("check_roadmap_quality_notes.py", 3),
    GateSpec("check_question_assets.py", 3),
    GateSpec("check_result_consistency.py", 4),
    GateSpec("check_abstract_no_formula.py", 4),
    GateSpec("check_abstract_one_page.py", 4),
    GateSpec("check_paper_emphasis.py", 4),
    GateSpec("check_latex_log.py", 4),
    GateSpec("check_drawing_contract.py", 4),
    GateSpec("check_roadmap_in_paper.py", 4),
    GateSpec("check_ai_prompt_paths.py", 4),
    GateSpec("check_template_adherence.py", 4),
    GateSpec("check_paper_section_whitelist.py", 4),
    GateSpec("check_model_building_rigor.py", 4),
    GateSpec("check_paper_layout_whitespace.py", 4),
    GateSpec("check_paper_internal_paths.py", 4),
    GateSpec("check_paper_body_forbidden_symbols.py", 4),
    GateSpec("check_paper_prose_style.py", 4),
    GateSpec("check_bibliography_sources.py", 4),
    GateSpec("check_support_material_catalog.py", 5),
    GateSpec("check_appendix_code_cleanliness.py", 5),
    GateSpec("check_appendix_code_equivalence.py", 5),
    GateSpec("check_body_page_count_minimum.py", 5),
    GateSpec("check_three_round_self_review.py", 5),
    GateSpec("check_python_3d_recommendation.py", 5),
    GateSpec("check_readme_agent_status.py", 5),
    GateSpec("check_deliverable_scorecard.py", 5),
)


def gates_for(stage: str) -> tuple[GateSpec, ...]:
    index = STAGES.index(stage)
    if stage == "step5":
        return GATES
    return tuple(
        gate
        for gate in GATES
        if gate.first_stage == index or (gate.repeat and gate.first_stage < index)
    )


def all_check_names() -> list[str]:
    return [gate.script for gate in GATES]


def validate_registry(base: Path | None = None) -> list[str]:
    base = base or Path(__file__).resolve().parent
    errors: list[str] = []
    registered = all_check_names()
    if len(registered) != len(set(registered)):
        errors.append("门禁注册表存在重复脚本")
    actual = sorted(path.name for path in base.glob("check_*.py"))
    missing = sorted(set(actual) - set(registered))
    unknown = sorted(set(registered) - set(actual))
    if missing:
        errors.append("存在未注册检查: " + "、".join(missing))
    if unknown:
        errors.append("注册了不存在的检查: " + "、".join(unknown))
    for gate in GATES:
        if not 0 <= gate.first_stage < len(STAGES):
            errors.append(f"{gate.script} 的阶段编号无效")
    return errors
