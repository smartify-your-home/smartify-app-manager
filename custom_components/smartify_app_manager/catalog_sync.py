"""Public GitHub discovery for Smartify apps (cached and rate-limited)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import re
import time

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import APPS, GITHUB_OWNER

_LOGGER = logging.getLogger(__name__)
API = "https://api.github.com"
REFRESH_SECONDS = 6 * 60 * 60
MANUAL_MIN_SECONDS = 10 * 60
SAFE_REPOSITORY = re.compile(r"^smartify-[A-Za-z0-9_.-]+$")
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "smartify-app-manager"}


def catalog_entries(remote_repos: list[dict], locks: dict) -> list[dict]:
    """Merge curated apps and newly discovered public repositories.

    Only published repositories under the pinned owner may be linked. Existing
    catalog IDs are stable so PIN-protected lock flags survive renames.
    """
    existing = {repo: (key, name, category, icon) for key, name, repo, category, icon in APPS}
    discovered = {}
    for item in remote_repos:
        if not isinstance(item, dict):
            continue
        repo = item.get("name", "")
        if (
            not isinstance(repo, str)
            or not SAFE_REPOSITORY.fullmatch(repo)
            or item.get("full_name") != f"{GITHUB_OWNER}/{repo}"
            or item.get("private")
            or item.get("archived")
            or repo == "smartify-app-manager"
        ):
            continue
        discovered[repo] = item

    result = []
    all_repos = list(existing)
    for name in sorted(discovered):
        if name not in existing:
            all_repos.append(name)
    for repo in all_repos:
        if repo in existing:
            key, name, category, icon = existing[repo]
        else:
            key, name, category, icon = repo, repo.replace("-", " ").title(), "new", "package"
        record = discovered.get(repo, {})
        result.append({
            "id": key, "name": name, "repo": repo,
            "category": category, "icon": icon,
            "locked": bool(locks.get(key, False)),
            "url": f"https://github.com/{GITHUB_OWNER}/{repo}",
            "new": repo not in existing,
            "latest_version": None,
            "release_url": None,
            "last_pushed_at": record.get("pushed_at"),
        })
    return result


async def _request_json(session, path: str):
    """Return validated JSON or None; never let network failure block HA."""
    try:
        async with session.get(
            f"{API}{path}", headers=HEADERS, timeout=ClientTimeout(total=12)
        ) as response:
            if response.status != 200:
                _LOGGER.debug("GitHub catalog request %s returned HTTP %s", path, response.status)
                return None
            return await response.json(content_type=None)
    except (ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.debug("GitHub catalog request failed for %s: %s", path, err)
        return None


async def async_sync_catalog(hass, state: dict, *, force: bool = False) -> bool:
    """Refresh in background or on explicit request; persist last good result.

    Rate-limit manual refreshes to 10 minutes. Normal refreshes occur every
    6 hours. No per-repo CI workflows, GitHub tokens or customer secrets.
    """
    async with state["sync_lock"]:
        now = time.monotonic()
        last_attempt = state.get("sync_attempt", 0.0)
        if last_attempt and now - last_attempt < (MANUAL_MIN_SECONDS if force else REFRESH_SECONDS):
            return False
        state["sync_attempt"] = now
        session = async_get_clientsession(hass)

        remote = await _request_json(
            session, f"/users/{GITHUB_OWNER}/repos?per_page=100&type=owner"
        )
        if not isinstance(remote, list):
            state["sync_error"] = "GitHub nicht erreichbar; letzter Katalog bleibt erhalten."
            return False

        settings = state["settings"]
        apps = catalog_entries(remote, settings.get("locks", {}))
        limiter = asyncio.Semaphore(4)

        async def get_release(app: dict):
            async with limiter:
                release = await _request_json(
                    session, f"/repos/{GITHUB_OWNER}/{app['repo']}/releases/latest"
                )
                if isinstance(release, dict):
                    tag = release.get("tag_name")
                    url = release.get("html_url")
                    if isinstance(tag, str) and tag and isinstance(url, str) and url.startswith(
                        f"https://github.com/{GITHUB_OWNER}/{app['repo']}/releases/"
                    ):
                        app["latest_version"] = tag
                        app["release_url"] = url

        await asyncio.gather(*(get_release(app) for app in apps))
        previous = settings.get("remote_catalog", [])
        previous_by_repo = {
            item.get("repo"): item for item in previous if isinstance(item, dict)
        }
        for app in apps:
            before = previous_by_repo.get(app["repo"], {})
            if not app["latest_version"] and before.get("latest_version"):
                app["latest_version"] = before["latest_version"]
                app["release_url"] = before.get("release_url")
        settings["remote_catalog"] = apps
        settings["last_synced"] = datetime.now(timezone.utc).isoformat()
        state["sync_error"] = None
        await state["store"].async_save(settings)
        return True


def current_catalog(settings: dict) -> list[dict]:
    """Use cached remote metadata, with an always-available curated fallback."""
    known = catalog_entries([], settings.get("locks", {}))
    cached = settings.get("remote_catalog", [])
    if not isinstance(cached, list):
        cached = []
    merged = {item["repo"]: item for item in known}
    for item in cached:
        if not isinstance(item, dict):
            continue
        repo = item.get("repo")
        if isinstance(repo, str) and SAFE_REPOSITORY.fullmatch(repo) and repo != "smartify-app-manager":
            if repo in merged:
                merged[repo].update({
                    "latest_version": item.get("latest_version"),
                    "release_url": item.get("release_url"),
                    "last_pushed_at": item.get("last_pushed_at"),
                })
            elif item.get("new"):
                merged[repo] = {
                    **item, "locked": bool(settings.get("locks", {}).get(item.get("id"), False))
                }
    return list(merged.values())
