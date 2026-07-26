"""
Ranking helpers shared by both stage1_pretest.ranking.pre_test_ranker and
stage2_posttest.ranking.post_test_ranker. Lives in src/common so the same
GitHub-fallback rule can never silently drift between the two stages.
"""

from __future__ import annotations

import pandas as pd


def safe_float(val, default: float = 0.0) -> float:
    if pd.isna(val) or val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


def github_score_for_row(row) -> float:
    """
    Missing or broken GitHub data gets a fair 30/100 floor, not a bare 0 —
    otherwise a candidate is punished by the full github weight just for a
    blank/failed field rather than actual weak evidence.
    """
    github_status = row.get("github_eval_status")
    github_val = row.get("github")
    no_link = pd.isna(github_val) or str(github_val).strip() == ""
    if github_status in ("skipped", "error") or no_link:
        return 30.0
    return safe_float(row.get("github_score"), 30.0)
