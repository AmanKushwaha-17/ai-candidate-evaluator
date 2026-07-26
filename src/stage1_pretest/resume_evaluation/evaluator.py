"""
Scores parsed resume text against a job description using an LLM. Stage 1 —
pre-test. Depends on src.common.llm_client.LLMClient (dependency inversion),
never a concrete provider directly.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from src.common.llm_client import LLMClient
from src.stage1_pretest.resume_evaluation.models import (
    EvaluationStatus,
    ResumeEvaluation,
    ResumeScore,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a technical recruiter evaluating a candidate's resume against a "
    "job description. Respond ONLY with a JSON object matching this schema: "
    '{"resume_score": <int 0-100>, "resume_score_reason": "<reason>"}. '
    "Score based on relevance of skills, projects, and academic background to "
    "the job description. The reason MUST be at most 2 short sentences and "
    "under 250 characters — be specific (reference an actual project or skill "
    "from the resume) but concise, not exhaustive."
)


class ResumeEvaluator:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    def evaluate(
        self,
        s_no: int | None,
        resume_text: str,
        job_description: str,
        cgpa: str | None = None,
        best_ai_project: str | None = None,
        research_work: str | None = None,
    ) -> ResumeEvaluation:
        if not resume_text or not resume_text.strip():
            return ResumeEvaluation(
                s_no=s_no,
                resume_score=None,
                resume_score_reason="No resume text available to evaluate.",
                status=EvaluationStatus.SKIPPED_NO_TEXT,
            )

        user_prompt = (
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            f"CANDIDATE RESUME TEXT:\n{resume_text[:6000]}\n\n"
            f"CGPA: {cgpa or 'not provided'}\n"
            f"Claimed best AI project: {best_ai_project or 'not provided'}\n"
            f"Claimed research work: {research_work or 'not provided'}"
        )

        try:
            raw = self._llm.complete_json(SYSTEM_PROMPT, user_prompt)
            score = ResumeScore.model_validate(raw)
            return ResumeEvaluation(
                s_no=s_no,
                resume_score=score.resume_score,
                resume_score_reason=score.resume_score_reason,
                status=EvaluationStatus.SCORED,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            logger.warning("Resume scoring failed for s_no=%s: %s", s_no, exc)
            return ResumeEvaluation(
                s_no=s_no,
                resume_score=None,
                resume_score_reason=f"LLM scoring failed: {exc}",
                status=EvaluationStatus.LLM_FAILED,
            )
