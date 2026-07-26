"""Scores a GitHub profile against a JD via LLM. Stage 1 — pre-test."""

from src.common.llm_client import GroqLLMClient, LLMClient
from src.stage1_pretest.github_evaluation.models import GitHubEvaluation, GitHubProfileData


class GitHubEvaluator:
    def __init__(self, llm_client: LLMClient | None = None, model_name: str = "llama-3.3-70b-versatile"):
        # Accept an injected client (shared key-rotation pool) or create one standalone
        self.llm = llm_client if llm_client is not None else GroqLLMClient(model=model_name)

    def evaluate(self, profile: GitHubProfileData, jd_text: str) -> GitHubEvaluation:
        system_prompt = f"""You are a technical recruiter evaluating a candidate's GitHub profile for this Job Description:
=== JOB DESCRIPTION ===
{jd_text}
=======================

Here is the candidate's parsed GitHub profile and top repositories:
=== GITHUB DATA ===
{profile.to_llm_string()}
===================

Evaluate their GitHub profile based ONLY on the evidence above.
Score out of 100 based on:
1. Tech Stack Relevance (Are they using tools mentioned in the JD?)
2. Project Complexity (Are they building real systems, or just basic tutorials?)
3. Evidence of Shipping (Are repos well-documented, with READMEs?)

Output your response EXACTLY as a JSON object with two keys:
{{
  "github_score": <int 0-100>,
  "github_score_reason": "<1-2 sentences explaining the score>"
}}
"""
        try:
            res_dict = self.llm.complete_json(system_prompt, "Evaluate this candidate.")
            return GitHubEvaluation(
                github_score=res_dict.get("github_score", 0),
                github_score_reason=res_dict.get("github_score_reason", "No reason provided"),
            )
        except Exception as e:
            print(f"Error evaluating GitHub profile for {profile.username}: {e}")
            return GitHubEvaluation(
                github_score=0,
                github_score_reason=f"Evaluation failed: {e}",
            )
