"""
Orchestrates Stage 1 only: resume evaluation -> GitHub evaluation ->
pre-test ranking. Never touches test scores — see src/stage2_posttest for
what happens after test results come in.
"""

import pandas as pd
from typing import Callable
from dotenv import load_dotenv 

load_dotenv()

from src.stage1_pretest.resume_evaluation.pipeline import ResumePipeline
from src.stage1_pretest.github_evaluation.pipeline import GitHubPipeline
from src.stage1_pretest.ranking.pre_test_ranker import rank_pre_test


def run_full_pipeline(
    df: pd.DataFrame,
    jd_text: str,
    progress_callback: Callable[[str, float], None] = None
) -> tuple[pd.DataFrame | None, str | None]:
    """
    Orchestrates the Stage 1 (pre-test) evaluation pipeline.
    progress_callback: function(status_message, progress_percentage 0.0-1.0)
    Returns: (pre_test_ranked_dataframe, error_message)
    """

    def update_progress(msg: str, pct: float):
        if progress_callback:
            progress_callback(msg, pct)

    try:
        total_rows = len(df)
        if total_rows == 0:
            return df, None

        from src.stage1_pretest.resume_evaluation.parser import ResumeParser
        from src.stage1_pretest.resume_evaluation.evaluator import ResumeEvaluator
        from src.common.llm_client import GroqLLMClient

        llm = GroqLLMClient(model="llama-3.3-70b-versatile")

        def resume_progress(current: int, total: int, name: str):
            update_progress(f"Evaluating Resume for {name}...", (current / total) * 0.45)

        resume_pipeline = ResumePipeline(
            parser=ResumeParser(),
            evaluator=ResumeEvaluator(llm_client=llm),
            progress_callback=resume_progress
        )

        # Bug 2 fix: pass the SAME llm instance so GitHub + Resume share key-rotation state
        github_pipeline = GitHubPipeline(jd_text, llm_client=llm)

        # Step 1: Resume Evaluation (iterates internally)
        df_scored, _ = resume_pipeline.run(df, jd_text)

        # Step 2: GitHub Evaluation
        github_scores = []
        github_reasons = []
        github_statuses = []

        # Bug 1 fix: use enumerate() for sequential counter — DataFrame index (i) is NOT
        # guaranteed to be 0-based sequential, especially after merges/resets
        for seq, (_, row) in enumerate(df_scored.iterrows()):
            pct_mid = 0.45 + ((seq + 1) / total_rows * 0.45)
            name = row.get("name", f"Candidate {seq + 1}")
            update_progress(f"Evaluating GitHub for {name}...", pct_mid)

            github_url = str(row.get("github", "")) if pd.notna(row.get("github")) else ""

            # Bug 4 fix: per-candidate try/except — one bad GitHub URL must NOT kill the
            # whole pipeline and discard all previously completed resume evaluations
            try:
                github_res = github_pipeline.process_candidate(github_url)
            except Exception as gh_exc:
                github_res = {
                    "github_score": 0,
                    "github_score_reason": f"Unexpected error: {gh_exc}",
                    "github_eval_status": "error",
                }

            github_scores.append(github_res["github_score"])
            github_reasons.append(github_res["github_score_reason"])
            github_statuses.append(github_res["github_eval_status"])

        df_scored["github_score"] = github_scores
        df_scored["github_score_reason"] = github_reasons
        df_scored["github_eval_status"] = github_statuses

        # Step 3: Pre-test ranking (resume + github + cgpa only)
        update_progress("Applying pre-test ranking logic...", 0.95)
        df_ranked = rank_pre_test(df_scored)

        update_progress("Pipeline complete!", 1.0)
        return df_ranked, None

    except Exception as e:
        return None, f"Pipeline failed: {str(e)}"
