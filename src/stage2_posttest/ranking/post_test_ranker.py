"""
Stage 2 ranking — run only AFTER test results have come in for the
shortlisted candidates (via src.stage2_posttest.score_merger). Uses the
full 5-weight scheme. Output: final_score / rank.
"""

from __future__ import annotations

import pandas as pd

from src.common.ranking_utils import github_score_for_row, safe_float


def rank_post_test(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    W_RESUME = 0.35
    W_GITHUB = 0.25
    W_TEST_CODE = 0.20
    W_TEST_LA = 0.15
    W_CGPA = 0.05

    scores = []
    for _, row in df.iterrows():
        resume_score = safe_float(row.get("resume_score"), 0.0)
        github_score = github_score_for_row(row)
        test_code = safe_float(row.get("test_code"), 0.0)
        test_la = safe_float(row.get("test_la"), 0.0)
        cgpa_normalized = safe_float(row.get("cgpa"), 0.0) * 10.0

        final_score = (
            (resume_score * W_RESUME)
            + (github_score * W_GITHUB)
            + (test_code * W_TEST_CODE)
            + (test_la * W_TEST_LA)
            + (cgpa_normalized * W_CGPA)
        )
        scores.append(round(final_score, 2))

    df_out = df.copy()
    df_out["final_score"] = scores
    df_out = df_out.sort_values(by="final_score", ascending=False).reset_index(drop=True)
    df_out["rank"] = df_out.index + 1

    cols = df_out.columns.tolist()
    front_cols = [
        "rank", "final_score", "name", "email",
        "resume_score", "resume_score_reason", "resume_eval_status",
        "github_score", "github_score_reason", "github_eval_status",
        "test_code", "test_la", "cgpa",
    ]
    final_cols = [c for c in front_cols if c in cols]
    final_cols += [c for c in cols if c not in final_cols]
    return df_out[final_cols]


# Backward-compatible alias.
rank_candidates = rank_post_test
