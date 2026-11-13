#!/usr/bin/env python3
"""Fail-closed global GitHub sync and customer publication allowlist for Cubi.

This tool performs *policy checks only*. The systemd sync/package services and
customer-serving gateway must enforce its decisions on Cubi before use.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_POLICY = Path('/etc/smartify/package-policy.json')
GITHUB_OWNER = 'smartify-your-home'
REPOSITORY = re.compile(r'^smartify-[A-Za-z0-9][A-Za-z0-9_.-]*$')
SUBDIR = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
ACTION = {'sync': 'sync', 'publish': 'publish'}


class PolicyError(ValueError):
    """Malformed, missing or ambiguous policy: deny all actions."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f'Duplicate JSON field: {key}')
        result[key] = value
    return result


def load_policy(filename: str | Path = DEFAULT_POLICY) -> dict:
    """Validate policy completely; no fallback to sync-all on errors."""
    try:
        with Path(filename).open(encoding='utf-8') as stream:
            policy = json.load(stream, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f'Cannot read policy: {exc}') from exc
    if not isinstance(policy, dict) or set(policy) != {'schema_version', 'default', 'github_owner', 'apps'}:
        raise PolicyError('Unexpected top-level policy fields')
    if type(policy['schema_version']) is not int or policy['schema_version'] != 1:
        raise PolicyError('Unsupported policy schema')
    if policy['default'] != 'deny':
        raise PolicyError('Policy must be default-deny')
    if policy['github_owner'] != GITHUB_OWNER:
        raise PolicyError('GitHub owner mismatch')
    apps = policy['apps']
    if not isinstance(apps, dict):
        raise PolicyError('apps must be an object')
    public_dirs = set()
    for repository, item in apps.items():
        if not REPOSITORY.fullmatch(repository) or '..' in repository:
            raise PolicyError(f'Invalid repository name: {repository!r}')
        if not isinstance(item, dict) or set(item) != {'sync', 'publish', 'release_dir'}:
            raise PolicyError(f'Invalid policy fields for {repository}')
        if type(item['sync']) is not bool or type(item['publish']) is not bool:
            raise PolicyError(f'Explicit boolean sync/publish required for {repository}')
        if item['publish'] and not item['sync']:
            raise PolicyError(f'Cannot publish without sync: {repository}')
        subdir = item['release_dir']
        if not isinstance(subdir, str) or not SUBDIR.fullmatch(subdir):
            raise PolicyError(f'Invalid release directory for {repository}')
        if subdir in public_dirs:
            raise PolicyError(f'Release directory used more than once: {subdir}')
        public_dirs.add(subdir)
    return policy


def is_allowed(policy: dict, repository: str, stage: str) -> bool:
    """Return False for missing entries; never derive authorization from GitHub."""
    if stage not in ACTION:
        raise PolicyError('Unknown policy stage')
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        return False
    entry = policy['apps'].get(repository)
    return entry is not None and entry[stage] is True


def approved_repositories(policy: dict, stage: str) -> list[str]:
    return sorted(repo for repo in policy['apps'] if is_allowed(policy, repo, stage))


def unexpected_public_directories(policy: dict, release_root: str | Path) -> list[str]:
    """Detect stray/public leftovers; do NOT delete them automatically."""
    allowed = {
        item['release_dir'] for item in policy['apps'].values() if item['publish']
    }
    root = Path(release_root)
    if not root.is_dir():
        raise PolicyError(f'Public release directory does not exist: {root}')
    return sorted(p.name for p in root.iterdir() if p.name not in allowed or p.is_symlink())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', default=str(DEFAULT_POLICY))
    subs = parser.add_subparsers(dest='command', required=True)
    check = subs.add_parser('check', help='Deny/permit a repository before one stage')
    check.add_argument('stage', choices=sorted(ACTION))
    check.add_argument('repository')
    listed = subs.add_parser('list', help='Emit repositories permitted for the stage')
    listed.add_argument('stage', choices=sorted(ACTION))
    subs.add_parser('validate', help='Validate policy, fail closed')
    audit = subs.add_parser('audit-public', help='Find unexpected files/dirs in static public release root')
    audit.add_argument('release_root')
    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.policy)
        if args.command == 'validate':
            print('VALID')
            return 0
        if args.command == 'check':
            if is_allowed(policy, args.repository, args.stage):
                print('ALLOW')
                return 0
            print('DENY', file=sys.stderr)
            return 1
        if args.command == 'list':
            for repo in approved_repositories(policy, args.stage):
                print(repo)
            return 0
        if args.command == 'audit-public':
            extras = unexpected_public_directories(policy, args.release_root)
            if extras:
                print('Unexpected public entries:\n' + '\n'.join(extras), file=sys.stderr)
                return 1
            print('CLEAN')
            return 0
    except PolicyError as exc:
        print(f'POLICY ERROR (all operations denied): {exc}', file=sys.stderr)
        return 2
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
