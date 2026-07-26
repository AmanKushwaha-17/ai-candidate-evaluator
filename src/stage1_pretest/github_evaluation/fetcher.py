"""Fetches GitHub profile + repo data via the REST API. Stage 1 — pre-test."""

import base64
import os
import re

import requests
from dotenv import load_dotenv

from src.stage1_pretest.github_evaluation.models import GitHubProfileData, GitHubRepo

load_dotenv()


class GitHubFetcher:
    GITHUB_API = "https://api.github.com"

    def __init__(self, max_repos: int = 5, max_readme_chars: int = 1000):
        self.max_repos = max_repos
        self.max_readme_chars = max_readme_chars
        self._token = os.getenv("GITHUB_TOKEN", "")
        self.headers = {
            "Accept": "application/vnd.github+json",
            **({"Authorization": f"Bearer {self._token}"} if self._token else {}),
        }

    def _fetch_json(self, url: str, extra_headers: dict | None = None) -> dict | list:
        headers = self.headers.copy()
        if extra_headers:
            headers.update(extra_headers)
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def _clean_markdown(self, text: str) -> str:
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # images
        text = re.sub(r"\[([^\]]+)\]\(.*?\)", r"\1", text)  # links
        text = re.sub(r"<[^>]+>", "", text)  # HTML
        return text

    def fetch_readme(self, username: str, repo_name: str) -> str:
        try:
            data = self._fetch_json(f"{self.GITHUB_API}/repos/{username}/{repo_name}/readme")
            content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
            lines = []
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                lines.append(line)

            text = self._clean_markdown("\n".join(lines))
            return text[: self.max_readme_chars] if text.strip() else "(README has no body text)"
        except Exception:
            return "(no README)"

    def fetch_topics(self, username: str, repo_name: str) -> list[str]:
        try:
            data = self._fetch_json(
                f"{self.GITHUB_API}/repos/{username}/{repo_name}/topics",
                extra_headers={"Accept": "application/vnd.github.mercy-preview+json"},
            )
            return data.get("names", [])
        except Exception:
            return []

    def fetch_profile(self, username: str) -> GitHubProfileData | None:
        try:
            user = self._fetch_json(f"{self.GITHUB_API}/users/{username}")
            repos_data = self._fetch_json(
                f"{self.GITHUB_API}/users/{username}/repos?per_page=30&sort=updated"
            )

            original_repos = [
                r for r in repos_data if not r.get("fork") and r["name"].lower() != username.lower()
            ]

            profile = GitHubProfileData(
                username=username,
                public_repos=user.get("public_repos", 0),
                followers=user.get("followers", 0),
                created_at=user.get("created_at"),
            )

            for r in original_repos[: self.max_repos]:
                repo_name = r["name"]
                topics = self.fetch_topics(username, repo_name)
                readme = self.fetch_readme(username, repo_name)

                profile.top_repos.append(
                    GitHubRepo(
                        name=repo_name,
                        language=r.get("language"),
                        stars=r.get("stargazers_count", 0),
                        pushed_at=r.get("pushed_at"),
                        description=r.get("description"),
                        topics=topics,
                        readme_content=readme,
                    )
                )

            return profile
        except Exception as e:
            print(f"Error fetching profile for {username}: {e}")
            return None
