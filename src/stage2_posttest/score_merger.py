"""
Merges test results onto the Stage 1 shortlist. Stage 2 — post-test only.

Join key: s_no (permanent, not a fallback).
If a candidate has no matching row in the test results sheet,
their test_la and test_code are set to 0 — they did not sit the test.
No fallback to the Response sheet values (different from old behaviour).
"""

from __future__ import annotations

import pandas as pd

JOIN_KEY = "s_no"


def merge_test_scores(
    candidates_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach test_la / test_code onto the Stage 1 candidate DataFrame by s_no.
    Missing rows → 0 (candidate absent / did not attempt the test).

    Returns a new DataFrame with columns:
        test_la, test_code, test_score_source
            ('test_result_sheet' | 'absent_zero')
    """
    if JOIN_KEY not in candidates_df.columns:
        raise ValueError(
            f"Candidate dataframe has no '{JOIN_KEY}' column — cannot merge test results."
        )

    if test_df is None or JOIN_KEY not in test_df.columns:
        # No test data at all → everyone gets 0
        out = candidates_df.copy()
        out["test_la"]          = 0.0
        out["test_code"]        = 0.0
        out["test_score_source"] = "absent_zero"
        return out

    # Normalise the join key to numeric in both frames
    left = candidates_df.copy()
    left[JOIN_KEY] = pd.to_numeric(left[JOIN_KEY], errors="coerce")

    # Drop test score columns from Stage 1 df — test_df is the authoritative source.
    # Without this, pandas creates test_la_x / test_la_y on merge and the lookup fails.
    for col in ("test_la", "test_code"):
        if col in left.columns:
            left = left.drop(columns=[col])

    right_cols = [JOIN_KEY] + [
        c for c in ("test_la", "test_code") if c in test_df.columns
    ]
    right = test_df[right_cols].copy()
    right[JOIN_KEY] = pd.to_numeric(right[JOIN_KEY], errors="coerce")
    right = right.drop_duplicates(subset=[JOIN_KEY])


    merged = left.merge(right, on=JOIN_KEY, how="left")

    # Fill missing test scores with 0
    for col in ("test_la", "test_code"):
        if col not in merged.columns:
            merged[col] = 0.0
        else:
            merged[col] = merged[col].fillna(0.0)

    merged["test_score_source"] = merged["test_la"].apply(
        lambda v: "test_result_sheet" if v != 0.0 else "absent_zero"
    )

    return merged


def match_summary(candidates_df: pd.DataFrame, test_df: pd.DataFrame | None) -> str:
    """Human-readable count of candidates matched to a test result."""
    if test_df is None or JOIN_KEY not in test_df.columns:
        return "No test results loaded — all candidates will receive 0 for test scores."

    merged = merge_test_scores(candidates_df, test_df)
    matched = (merged["test_score_source"] == "test_result_sheet").sum()
    total   = len(merged)
    absent  = total - matched
    return (
        f"{matched}/{total} shortlisted candidates matched via s_no "
        f"({absent} absent → test scores set to 0). "
        f"(Evaluating only the {total} candidates to whom the test link was sent.)"
    )
