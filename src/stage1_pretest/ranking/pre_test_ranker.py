"""
Stage 1 ranking — decides who gets sent a test link.

Deliberately blind to test_la/test_code, even if those columns already exist
on the incoming dataframe (they can — the Response sheet in the sample data
carries them). Only resume_score, github_score, and cgpa are used.
"""

from __future__ import annotations

import pandas as pd

from src.common.ranking_utils import github_score_for_row, safe_float


def rank_pre_test(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weights: the original 5-weight scheme's resume/github/cgpa shares
    (0.35 / 0.25 / 0.05 = 0.65 of the full budget), renormalized to sum to
    1.0 — so a candidate isn't penalized for two dimensions that haven't
    happened yet.

    Output columns: pre_test_score / pre_test_rank — never final_score/rank,
    so this can't be mistaken for the post-test result.
    """
    if df.empty:
        return df

    base_weights = {"resume": 0.35, "github": 0.25, "cgpa": 0.05}
    weight_sum = sum(base_weights.values())
    w_resume = base_weights["resume"] / weight_sum
    w_github = base_weights["github"] / weight_sum
    w_cgpa = base_weights["cgpa"] / weight_sum

    scores = []
    for _, row in df.iterrows():
        resume_score = safe_float(row.get("resume_score"), 0.0)
        github_score = github_score_for_row(row)
        cgpa_normalized = safe_float(row.get("cgpa"), 0.0) * 10.0

        pre_test_score = (
            (resume_score * w_resume) + (github_score * w_github) + (cgpa_normalized * w_cgpa)
        )
        scores.append(round(pre_test_score, 2))

    df_out = df.copy()
    df_out["pre_test_score"] = scores
    df_out = df_out.sort_values(by="pre_test_score", ascending=False).reset_index(drop=True)
    df_out["pre_test_rank"] = df_out.index + 1

    cols = df_out.columns.tolist()
    front_cols = [
        "pre_test_rank", "pre_test_score", "name", "email",
        "resume_score", "resume_score_reason", "resume_eval_status",
        "github_score", "github_score_reason", "github_eval_status",
        "cgpa",
    ]
    final_cols = [c for c in front_cols if c in cols]
    final_cols += [c for c in cols if c not in final_cols]
    return df_out[final_cols]
