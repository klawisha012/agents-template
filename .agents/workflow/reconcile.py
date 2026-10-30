#!/usr/bin/env python3
"""Reconcile labeled GitHub issues using the shared roster and issue metadata."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from distribute import execute, fetch_issue, make_plan, run_gh, validate

METADATA = re.compile(r"<!--\s*agent-distribution:\s*(\{[^\n]*\})\s*-->")


def pages(path):
    page = 1
    result = []
    while True:
        separator = "&" if "?" in path else "?"
        data = json.loads(run_gh("api", f"{path}{separator}per_page=100&page={page}"))
        if not isinstance(data, list):
            raise ValueError(f"expected list from {path}")
        result.extend(data)
        if len(data) < 100:
            return result
        page += 1


def build_batch(repo):
    raw = pages(f"repos/{repo}/issues?state=open&labels=ready-for-agent")
    items, skipped = [], []
    for issue in raw:
        if "pull_request" in issue:
            continue
        n = issue["number"]
        matches = METADATA.findall(issue.get("body") or "")
        if len(matches) != 1:
            skipped.append({"issue": n, "reason": "missing or ambiguous distribution metadata"})
            continue
        try:
            metadata = json.loads(matches[0])
            if not isinstance(metadata, dict) or not all(k in metadata for k in ("skills", "estimate", "blocked_by")):
                raise ValueError("metadata needs skills, estimate, blocked_by")
            dependencies = pages(f"repos/{repo}/issues/{n}/dependencies/blocked_by")
            if any(not str(d.get("repository_url", "")).lower().endswith("/repos/" + repo.lower()) for d in dependencies):
                raise ValueError("cross-repository dependency needs manual review")
            blockers = metadata["blocked_by"]
            if not isinstance(blockers, list):
                raise ValueError("blocked_by must be a list")
            item = {"number": n, "skills": metadata["skills"], "estimate": metadata["estimate"],
                    "blocked_by": list(set(blockers + [d["number"] for d in dependencies]))}
            # Validate individual metadata before allowing it to affect any other issue.
            validate({"repository": repo, "members": [{"login": "example", "skills": [], "availability": {"state": "away"}}]}, {"issues": [item]})
            items.append(item)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            skipped.append({"issue": n, "reason": str(exc)})
    return items, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        team = json.loads(args.team.read_text(encoding="utf-8-sig"))
        repo = team["repository"]
        env_repo = os.environ.get("GITHUB_REPOSITORY")
        if env_repo and env_repo.casefold() != repo.casefold():
            raise ValueError("roster repository does not match the GitHub Actions repository")
        # Validate repository and roster even if the queue is empty.
        validate(team, {"issues": [{"number": 1}]})
        items, skipped = build_batch(repo)
        if not items:
            print(json.dumps({"repository": repo, "results": [], "skipped": skipped}, ensure_ascii=False, indent=2))
            return 0
        _, members, ordered = validate(team, {"issues": items})
        for member in members:
            if member["availability"]["available"]:
                run_gh("api", f"repos/{repo}/assignees/{member['login']}")
        ids = {t["number"] for t in ordered} | {b for t in ordered for b in t["blocked_by"]}
        issues = {n: fetch_issue(repo, n) for n in sorted(ids)}
        plan = make_plan(members, ordered, issues)
        failed = execute(repo, plan, members) if args.apply else False
        print(json.dumps({"repository": repo, "mode": "apply" if args.apply else "preview", "results": plan, "skipped": skipped}, ensure_ascii=False, indent=2))
        return 1 if failed or any(r["action"] in ("skipped_changed", "skipped_expired", "conflict_after_write", "failed") for r in plan) else 0
    except (ValueError, TypeError, RuntimeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"Reconciliation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
