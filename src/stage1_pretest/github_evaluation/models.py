"""Pydantic models for GitHub evaluation. Stage 1 — pre-test."""

from pydantic import BaseModel, Field


class GitHubRepo(BaseModel):
    name: str
    language: str | None = None
    stars: int = 0
    pushed_at: str | None = None
    description: str | None = None
    topics: list[str] = Field(default_factory=list)
    readme_content: str = ""


class GitHubProfileData(BaseModel):
    username: str
    public_repos: int = 0
    followers: int = 0
    created_at: str | None = None
    top_repos: list[GitHubRepo] = Field(default_factory=list)

    def to_llm_string(self) -> str:
        parts = [
            f"Public Repos: {self.public_repos}",
            f"Followers: {self.followers}",
            f"Account Created: {self.created_at}",
            "\nTop Recent Repositories:",
        ]
        for i, r in enumerate(self.top_repos, 1):
            topics_str = ", ".join(r.topics) if r.topics else "None"
            repo_info = (
                f"\n[{i}] {r.name} (Language: {r.language}, Stars: {r.stars})\n"
                f"Description: {r.description or '(no description)'}\n"
                f"Topics: {topics_str}\n"
                f"README Snippet ({len(r.readme_content)} chars):\n{r.readme_content}\n"
            )
            parts.append(repo_info)
        return "\n".join(parts)


class GitHubEvaluation(BaseModel):
    github_score: int = Field(default=0, ge=0, le=100)
    github_score_reason: str = ""
