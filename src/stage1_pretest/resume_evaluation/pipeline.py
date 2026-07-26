"""
Runs parse + evaluate for every candidate row in a DataFrame. Stage 1 —
pre-test batch runner.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

import pandas as pd

from src.stage1_pretest.resume_evaluation.evaluator import ResumeEvaluator
from src.stage1_pretest.resume_evaluation.models import EvaluationStatus, ResumeEvaluation
from src.stage1_pretest.resume_evaluation.parser import ResumeParser

logger = logging.getLogger(__name__)


class ResumePipeline:
    """Runs parse + evaluate for every candidate row in a DataFrame."""

    def __init__(
        self,
        parser: ResumeParser,
        evaluator: ResumeEvaluator,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ):
        self._parser = parser
        self._evaluator = evaluator
        self._progress = progress_callback or _default_progress

    def run(
        self,
        candidates_df: pd.DataFrame,
        job_description: str,
    ) -> tuple[pd.DataFrame, list[ResumeEvaluation]]:
        total = len(candidates_df)
        evaluations: list[ResumeEvaluation] = []

        for i, (_, row) in enumerate(candidates_df.iterrows(), start=1):
            s_no = _safe_int(row.get("s_no"))
            name = str(row.get("name", f"candidate #{i}"))
            resume_link = row.get("resume")
            cgpa = _safe_str(row.get("cgpa"))
            best_ai_project = _safe_str(row.get("best_ai_project"))
            research_work = _safe_str(row.get("research_work"))

            self._progress(i, total, name)
            t0 = time.perf_counter()

            try:
                parsed = self._parser.parse(s_no=s_no, resume_link=resume_link)
                evaluation = self._evaluator.evaluate(
                    s_no=s_no,
                    resume_text=parsed.text,
                    job_description=job_description,
                    cgpa=cgpa,
                    best_ai_project=best_ai_project,
                    research_work=research_work,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected error for s_no=%s (%s): %s", s_no, name, exc)
                evaluation = ResumeEvaluation(
                    s_no=s_no,
                    resume_score=None,
                    resume_score_reason=f"Pipeline error: {exc}",
                    status=EvaluationStatus.LLM_FAILED,
                )

            elapsed = time.perf_counter() - t0
            logger.info(
                "s_no=%s  status=%s  score=%s  took=%.2fs",
                s_no, evaluation.status.value, evaluation.resume_score, elapsed,
            )
            evaluations.append(evaluation)
            if i < total:
                time.sleep(1)  # pace requests to stay within Groq's token-per-minute limit

        results_df = _join_results(candidates_df, evaluations)
        return results_df, evaluations


def _default_progress(current: int, total: int, name: str) -> None:
    print(f"[{current}/{total}] Evaluating: {name}")


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value) -> str | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    s = str(value).strip()
    return s if s else None


def _join_results(df: pd.DataFrame, evaluations: list[ResumeEvaluation]) -> pd.DataFrame:
    result = df.copy()

    eval_by_sno: dict[int, ResumeEvaluation] = {}
    positional: list[ResumeEvaluation] = []
    for ev in evaluations:
        if ev.s_no is not None:
            eval_by_sno[ev.s_no] = ev
        else:
            positional.append(ev)

    scores: list[int | None] = []
    reasons: list[str] = []
    statuses: list[str] = []

    for i, (_, row) in enumerate(df.iterrows()):
        s_no = _safe_int(row.get("s_no"))
        ev = eval_by_sno.get(s_no) if s_no is not None else (positional[i] if i < len(positional) else None)
        if ev:
            scores.append(ev.resume_score)
            reasons.append(ev.resume_score_reason)
            statuses.append(ev.status.value)
        else:
            scores.append(None)
            reasons.append("not evaluated")
            statuses.append("missing")

    result["resume_score"] = scores
    result["resume_score_reason"] = reasons
    result["resume_eval_status"] = statuses

    return result
