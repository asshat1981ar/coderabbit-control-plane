"""Narrow GitHub REST adapter used only for repository synchronization."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .errors import ExternalRepositoryError


@dataclass(slots=True)
class GitHubRestClient:
    """Minimal GitHub repository client with credentials sourced from process environment."""

    _token: str
    api_base: str = "https://api.github.com"
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> "GitHubRestClient":
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ExternalRepositoryError("GITHUB_TOKEN is required for GitHub synchronization")
        return cls(_token=token)

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> object | None:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.api_base.rstrip("/") + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "coderabbit-control-plane",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            detail = exc.read().decode("utf-8", errors="replace")
            raise ExternalRepositoryError(
                f"GitHub API {method} {path} failed with HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except URLError as exc:
            raise ExternalRepositoryError(f"GitHub API {method} {path} failed: {exc.reason}") from exc
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalRepositoryError(
                f"GitHub API {method} {path} returned invalid JSON"
            ) from exc

    @staticmethod
    def _repo_path(repository: str) -> str:
        parts = repository.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ExternalRepositoryError(f"invalid GitHub repository name: {repository}")
        return f"/repos/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}"

    def get_head(self, repository: str, branch: str) -> str:
        payload = self._request(
            "GET",
            f"{self._repo_path(repository)}/git/ref/heads/{quote(branch, safe='')}",
        )
        if not isinstance(payload, Mapping):
            raise ExternalRepositoryError("GitHub ref response is not an object")
        obj = payload.get("object")
        if not isinstance(obj, Mapping) or not isinstance(obj.get("sha"), str):
            raise ExternalRepositoryError("GitHub ref response is missing object.sha")
        return str(obj["sha"])

    def create_branch(self, repository: str, branch: str, sha: str) -> None:
        self._request(
            "POST",
            f"{self._repo_path(repository)}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )

    def read_file(self, repository: str, path: str, ref: str) -> str | None:
        payload = self._request(
            "GET",
            f"{self._repo_path(repository)}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}",
            allow_not_found=True,
        )
        if payload is None:
            return None
        if not isinstance(payload, Mapping) or payload.get("encoding") != "base64":
            raise ExternalRepositoryError(f"GitHub contents response is invalid for {path}")
        content = payload.get("content")
        if not isinstance(content, str):
            raise ExternalRepositoryError(f"GitHub contents response is missing content for {path}")
        try:
            return base64.b64decode(content).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExternalRepositoryError(f"GitHub contents response is not UTF-8 text for {path}") from exc

    def write_files(
        self,
        repository: str,
        branch: str,
        files: Mapping[str, str],
        message: str,
    ) -> str:
        parent_sha = self.get_head(repository, branch)
        commit_payload = self._request(
            "GET", f"{self._repo_path(repository)}/git/commits/{quote(parent_sha, safe='')}"
        )
        if not isinstance(commit_payload, Mapping):
            raise ExternalRepositoryError("GitHub commit response is not an object")
        tree = commit_payload.get("tree")
        if not isinstance(tree, Mapping) or not isinstance(tree.get("sha"), str):
            raise ExternalRepositoryError("GitHub commit response is missing tree.sha")

        tree_entries = []
        for path, content in sorted(files.items()):
            blob = self._request(
                "POST",
                f"{self._repo_path(repository)}/git/blobs",
                {"content": content, "encoding": "utf-8"},
            )
            if not isinstance(blob, Mapping) or not isinstance(blob.get("sha"), str):
                raise ExternalRepositoryError(f"GitHub blob response is invalid for {path}")
            tree_entries.append(
                {"path": path, "mode": "100644", "type": "blob", "sha": str(blob["sha"])}
            )

        new_tree = self._request(
            "POST",
            f"{self._repo_path(repository)}/git/trees",
            {"base_tree": str(tree["sha"]), "tree": tree_entries},
        )
        if not isinstance(new_tree, Mapping) or not isinstance(new_tree.get("sha"), str):
            raise ExternalRepositoryError("GitHub tree response is invalid")

        new_commit = self._request(
            "POST",
            f"{self._repo_path(repository)}/git/commits",
            {"message": message, "tree": str(new_tree["sha"]), "parents": [parent_sha]},
        )
        if not isinstance(new_commit, Mapping) or not isinstance(new_commit.get("sha"), str):
            raise ExternalRepositoryError("GitHub create-commit response is invalid")
        commit_sha = str(new_commit["sha"])
        self._request(
            "PATCH",
            f"{self._repo_path(repository)}/git/refs/heads/{quote(branch, safe='')}",
            {"sha": commit_sha, "force": False},
        )
        return commit_sha

    def open_pull_request(
        self,
        repository: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> int:
        payload = self._request(
            "POST",
            f"{self._repo_path(repository)}/pulls",
            {"head": head, "base": base, "title": title, "body": body, "draft": False},
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("number"), int):
            raise ExternalRepositoryError("GitHub pull-request response is invalid")
        return int(payload["number"])
