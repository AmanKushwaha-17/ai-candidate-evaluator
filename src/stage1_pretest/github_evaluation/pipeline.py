"""Per-candidate GitHub fetch + evaluate orchestration. Stage 1 — pre-test."""

import time
from typing import TypedDict

from src.stage1_pretest.github_evaluation.evaluator import GitHubEvaluator
from src.stage1_pretest.github_evaluation.fetcher import GitHubFetcher
from src.common.llm_client import LLMClient


class GitHubPipelineResult(TypedDict):
    github_score: int
    github_score_reason: str
    github_eval_status: str


class GitHubPipeline:
    def __init__(self, jd_text: str, llm_client: LLMClient | None = None):
        self.jd_text = jd_text
        self.fetcher = GitHubFetcher()
        
        self.evaluator = GitHubEvaluator(llm_client=llm_client)

    def process_candidate(self, github_url: str) -> GitHubPipelineResult:
        if not github_url or not isinstance(github_url, str) or "github.com/" not in github_url:
            return {
                "github_score": 0,
                "github_score_reason": "No valid GitHub URL provided.",
                "github_eval_status": "skipped",
            }

        parts = github_url.rstrip("/").split("/")
        if len(parts) < 1:
            return {
                "github_score": 0,
                "github_score_reason": "Invalid GitHub URL format.",
                "github_eval_status": "error",
            }

        username = parts[-1]

        profile = self.fetcher.fetch_profile(username)
        if not profile:
            return {
                "github_score": 0,
                "github_score_reason": "Failed to fetch GitHub profile or user does not exist.",
                "github_eval_status": "error",
            }

        if profile.public_repos == 0:
            return {
                "github_score": 0,
                "github_score_reason": "Candidate has no public repositories.",
                "github_eval_status": "scored",
            }

        evaluation = self.evaluator.evaluate(profile, self.jd_text)

        time.sleep(1)  # rate limit safety

        return {
            "github_score": evaluation.github_score,
            "github_score_reason": evaluation.github_score_reason,
            "github_eval_status": "scored",
        }
