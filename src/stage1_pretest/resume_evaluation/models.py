"""
Pydantic models for the resume-evaluation module only (Stage 1 — pre-test).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ParseStatus(str, Enum):
    OK = "ok"
    NO_LINK = "no_link"
    DOWNLOAD_FAILED = "download_failed"
    NOT_A_PDF = "not_a_pdf"
    EXTRACTION_FAILED = "extraction_failed"


class ParsedResume(BaseModel):
    """Output of ResumeParser.parse() for one candidate."""

    s_no: int | None = None
    status: ParseStatus
    text: str = ""
    char_count: int = 0
    error: str | None = None


class ResumeScore(BaseModel):
    """
    The exact shape we require the LLM to return. Validating raw LLM JSON
    against this model is what makes a small/free-tier model safe to use —
    if it drifts from the schema, we catch it here, not downstream.
    """

    resume_score: int = Field(ge=0, le=100, description="0-100 relevance score against the JD")
    resume_score_reason: str = Field(min_length=1, max_length=400)


class EvaluationStatus(str, Enum):
    SCORED = "scored"
    SKIPPED_NO_TEXT = "skipped_no_text"
    LLM_FAILED = "llm_failed"


class ResumeEvaluation(BaseModel):
    """What ResumeEvaluator.evaluate() returns per candidate — score plus provenance."""

    s_no: int | None = None
    resume_score: int | None = None
    resume_score_reason: str
    status: EvaluationStatus
