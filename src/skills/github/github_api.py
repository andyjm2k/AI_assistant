"""Minimal GitHub REST API client."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import GitHubApiError


class GitHubApiClient:
    """Thin wrapper around GitHub REST endpoints used by CATBot."""

    def __init__(
        self,
        token: str,
        owner: str,
        repo: str,
        api_base: str = "https://api.github.com",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.api_base = api_base.rstrip("/")
        self.client = httpx.Client(
            timeout=timeout_seconds,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "GitHubApiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_base}{path}"
        response = self.client.request(method, url, params=params, json=payload)
        if response.status_code >= 400:
            message = response.text
            try:
                data = response.json()
                message = data.get("message", message)
            except ValueError:
                pass
            raise GitHubApiError(f"GitHub API {method} {path} failed ({response.status_code}): {message}")
        if response.content:
            return response.json()
        return {}

    def get_repository(self) -> dict[str, Any]:
        return self._request("GET", f"/repos/{self.owner}/{self.repo}")

    def get_rate_limit(self) -> dict[str, Any]:
        return self._request("GET", "/rate_limit")

    def create_pull_request(self, title: str, head: str, base: str, body: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/pulls",
            payload={"title": title, "head": head, "base": base, "body": body},
        )

    def list_pull_requests(
        self,
        *,
        state: str = "open",
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repo}/pulls",
            params={
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": max(1, min(int(per_page), 100)),
                "page": max(1, int(page)),
            },
        )
        return payload if isinstance(payload, list) else []

    def create_release(
        self,
        tag_name: str,
        *,
        name: str | None = None,
        body: str = "",
        prerelease: bool = False,
        draft: bool = False,
        target_commitish: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tag_name": tag_name,
            "name": name or tag_name,
            "body": body,
            "prerelease": prerelease,
            "draft": draft,
        }
        if target_commitish:
            payload["target_commitish"] = target_commitish
        return self._request("POST", f"/repos/{self.owner}/{self.repo}/releases", payload=payload)
