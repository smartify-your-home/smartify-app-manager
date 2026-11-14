#!/usr/bin/env python3
"""Privately fetch *published* release snapshots for globally approved repos.

Uses a read-only fine-grained GitHub token stored as a protected local file.
Does not clone arbitrary discovered repositories or publish any files itself.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import build_opener, HTTPRedirectHandler, Request

from package_policy import is_allowed, load_policy

RELEASE_TAG = re.compile(r"^v?\d+\.\d+\.\d+$")
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ENTRIES = 2500
ALLOWED_REDIRECT_HOSTS = {"codeload.github.com", "github.com"}


class FetchError(ValueError):
    pass


class DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT = build_opener(DenyRedirect)


def token_from_file(filename: str | Path) -> str:
    path = Path(filename)
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise FetchError("GitHub token file must not be readable/writable by group or others")
    token = path.read_text(encoding="utf-8").strip()
    if not token or "\n" in token or "\r" in token or len(token) > 512:
        raise FetchError("Invalid GitHub token file")
    return token


def github_request_json(url: str, token: str) -> tuple[dict, bool]:
    """Get a release: try the scoped PAT, then anonymous for public repos.

    Fine-grained tokens restricted to selected private repos can receive a
    misleading GitHub HTTP 404 when querying a different *public* repo.
    Fallback is only allowed for HTTP 404; private repositories still require
    a working token. The boolean says whether archive fetch needs the token.
    """
    if urlparse(url).hostname != "api.github.com":
        raise FetchError("Unexpected metadata host")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "smartify-cubi-private-release-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    used_token = True
    try:
        with NO_REDIRECT.open(Request(url, headers=headers), timeout=25) as response:
            raw = response.read(262145)
    except HTTPError as err:
        if err.code != 404:
            raise FetchError(f"GitHub release metadata: HTTP {err.code}") from err
        # Do not forward credentials to the public/anonymous request.
        public_headers = {key: value for key, value in headers.items()
                          if key != "Authorization"}
        try:
            with NO_REDIRECT.open(Request(url, headers=public_headers), timeout=25) as response:
                raw = response.read(262145)
            used_token = False
        except HTTPError as public_err:
            raise FetchError(
                f"Release not available: authenticated HTTP 404, "
                f"anonymous HTTP {public_err.code}. Check GitHub token "
                "repository selection/permissions and published releases."
            ) from public_err
        except (URLError, TimeoutError) as public_err:
            raise FetchError(
                f"Public release retry failed: {type(public_err).__name__}"
            ) from public_err
    except (URLError, TimeoutError) as err:
        raise FetchError(f"GitHub release metadata request failed: {type(err).__name__}") from err
    if len(raw) > 262144:
        raise FetchError("Release metadata oversized")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as err:
        raise FetchError("Invalid release JSON") from err
    if not isinstance(data, dict):
        raise FetchError("Invalid release metadata")
    return data, used_token

def fetch_private_tarball(url: str, token: str | None) -> bytes:
    """One GitHub API redirect only; never forward the private token to a redirect."""
    if urlparse(url).hostname != "api.github.com":
        raise FetchError("Unexpected tarball origin")
    request_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "smartify-cubi-private-release-sync",
    }
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=request_headers)
    try:
        with NO_REDIRECT.open(req, timeout=40) as response:
            raw = response.read(MAX_ARCHIVE_BYTES + 1)
    except HTTPError as redir:
        if redir.code not in (301, 302, 303, 307, 308):
            raise FetchError(f"GitHub archive request failed: HTTP {redir.code}") from redir
        target = redir.headers.get("Location", "")
        parsed = urlparse(target)
        if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_REDIRECT_HOSTS
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise FetchError("Unsafe GitHub archive redirect")
        try:
            with NO_REDIRECT.open(Request(target, headers={
                "User-Agent": "smartify-cubi-private-release-sync"
            }), timeout=50) as response:
                raw = response.read(MAX_ARCHIVE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise FetchError(f"Private archive retrieval failed: {type(exc).__name__}") from exc
    except (URLError, TimeoutError) as exc:
        raise FetchError(f"GitHub tarball retrieval failed: {type(exc).__name__}") from exc
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise FetchError("Release tarball too large")
    return raw


def unpack_release(data: bytes, destination: Path) -> None:
    """Reject traversal, symlinks, hardlinks, devices, zip bombs and escaped roots."""
    import io
    destination.mkdir(parents=True, exist_ok=False)
    total_size = 0
    names = set()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        members = tar.getmembers()
        if len(members) > MAX_ENTRIES:
            raise FetchError("Too many archive entries")
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                    or member.issym() or member.islnk() or not (member.isdir() or member.isfile())):
                raise FetchError("Unsafe release member")
            # GitHub archives have one dynamic root directory.
            if len(path.parts) < 2:
                continue
            rel = PurePosixPath(*path.parts[1:])
            if rel in names:
                raise FetchError("Duplicate release member")
            names.add(rel)
            target = destination.joinpath(*rel.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise FetchError("Archive traversal")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            total_size += member.size
            if member.size > 20 * 1024 * 1024 or total_size > MAX_UNCOMPRESSED_BYTES:
                raise FetchError("Release files too large")
            target.parent.mkdir(parents=True, exist_ok=True)
            input_file = tar.extractfile(member)
            if input_file is None:
                raise FetchError("Empty archive member")
            with target.open("xb") as output:
                remaining = member.size
                while remaining > 0:
                    chunk = input_file.read(min(65536, remaining))
                    if not chunk:
                        raise FetchError("Truncated archive")
                    output.write(chunk)
                    remaining -= len(chunk)


def sync_approved(policy_file: Path, token_file: Path, checkouts: Path) -> list[str]:
    policy = load_policy(policy_file)
    token = token_from_file(token_file)
    checkouts.mkdir(parents=True, exist_ok=True)
    synced = []
    for repo in sorted(policy["apps"]):
        if not is_allowed(policy, repo, "sync"):
            continue
        url = f"https://api.github.com/repos/{policy['github_owner']}/{repo}/releases/latest"
        try:
            release, authenticated = github_request_json(url, token)
        except FetchError as err:
            raise FetchError(f"{repo}: {err}") from err
        tag = release.get("tag_name")
        if (not isinstance(tag, str) or not RELEASE_TAG.fullmatch(tag)
                or release.get("draft") is not False
                or release.get("prerelease") is not False
                or not release.get("published_at")):
            raise FetchError(f"No approved published release for {repo}")
        checkout = checkouts / repo
        receipt = checkout / "cubi-release.json"
        if receipt.is_file() and checkout.joinpath("src").is_dir():
            if json.loads(receipt.read_text(encoding="utf-8")).get("tag") == tag:
                synced.append(f"{repo} {tag}: unchanged")
                continue
        archive_url = (
            f"https://api.github.com/repos/{policy['github_owner']}/{repo}"
            f"/tarball/{quote(tag, safe='')}"
        )
        try:
            archive = fetch_private_tarball(archive_url, token if authenticated else None)
        except FetchError as err:
            raise FetchError(f"{repo}: {err}") from err
        # Never stage beneath the public Tailscale Serve root.
        with tempfile.TemporaryDirectory(prefix=".cubi-fetch-", dir=checkouts) as temp:
            staged = Path(temp) / repo
            staged.mkdir()
            unpack_release(archive, staged / "src")
            (staged / "cubi-release.json").write_text(
                json.dumps({
                    "tag": tag,
                    "published_release": True,
                    "published_at": release["published_at"],
                    "repo": repo,
                }, indent=2) + "\n", encoding="utf-8"
            )
            old = checkouts / (repo + ".previous")
            if old.exists():
                shutil.rmtree(old)
            if checkout.exists():
                os.replace(checkout, old)
            os.replace(staged, checkout)
            if old.exists():
                shutil.rmtree(old)
        synced.append(f"{repo} {tag}: fetched")
    return synced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default="/etc/smartify/package-policy.json")
    parser.add_argument("--token", default="/etc/smartify/github-token")
    parser.add_argument("--checkouts", required=True)
    args = parser.parse_args(argv)
    for message in sync_approved(Path(args.policy), Path(args.token), Path(args.checkouts)):
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
