#!/usr/bin/env python3
"""Give unassigned ready-for-agent tickets an owner by team role and load."""
import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
METADATA = re.compile(r"<!--\s*agent-distribution:\s*(\{[^\n]*\})\s*-->")


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return float(value)


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive issue number")
    return value


def validate_team(team):
    if not isinstance(team, dict):
        raise ValueError("team must be a JSON object")
    repo = team.get("repository")
    if not isinstance(repo, str) or not REPOSITORY.fullmatch(repo) or repo.casefold() == "owner/repository":
        raise ValueError("team.repository must be the actual OWNER/REPOSITORY")
    catalog = team.get("roles")
    if not isinstance(catalog, dict) or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in catalog.items()):
        raise ValueError("team.roles must map each role name to a non-empty description")
    roles = {k.strip().casefold() for k in catalog}
    if len(roles) != len(catalog):
        raise ValueError("duplicate role in team.roles")
    members = team.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("team.members must contain at least one real participant")
    normalized = []
    seen = set()
    for m in members:
        if not isinstance(m, dict):
            raise ValueError("each member must be an object")
        login = m.get("login")
        if not isinstance(login, str) or not LOGIN.fullmatch(login) or login.casefold() == "replace-with-real-github-login":
            raise ValueError(f"invalid or placeholder GitHub login: {login!r}")
        if "skills" in m or "availability" in m:
            raise ValueError(f"{login}: skills was replaced by roles, and availability is no longer used")
        if login.casefold() in seen:
            raise ValueError(f"duplicate team member: {login}")
        seen.add(login.casefold())
        own = m.get("roles", [])
        if not isinstance(own, list) or any(not isinstance(r, str) for r in own):
            raise ValueError(f"roles of {login} must be a list of role names")
        own = {r.strip().casefold() for r in own}
        if own - roles:
            raise ValueError(f"{login} has roles missing from team.roles: {', '.join(sorted(own - roles))}")
        normalized.append({"login": login, "capacity": positive(m.get("capacity", 1), f"capacity of {login}"), "roles": own})
    return repo, roles, normalized


def parse_ticket(n, body, roles):
    matches = METADATA.findall(body or "")
    if len(matches) != 1:
        raise ValueError("missing or ambiguous distribution metadata")
    data = json.loads(matches[0])
    if not isinstance(data, dict) or "role" not in data:
        raise ValueError('metadata needs "role" (null when any member may take the ticket)')
    role = data["role"]
    if role is not None:
        if not isinstance(role, str) or role.strip().casefold() not in roles:
            raise ValueError(f"unknown role {role!r}; add it to team.roles or fix the ticket")
        role = role.strip().casefold()
    parts = data.get("parts", [])
    if not isinstance(parts, list):
        raise ValueError("parts must be a list of issue numbers")
    parts = sorted({number(p, f"part of #{n}") for p in parts})
    if parts and role is not None:
        raise ValueError("a verification ticket with parts must have role null")
    return {"number": n, "role": role, "estimate": positive(data.get("estimate", 1), f"estimate of #{n}"), "parts": parts}


def run_gh(*args):
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"cannot execute gh: {exc}") from exc
    if result.returncode:
        raise RuntimeError(f"gh failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


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


def fetch_issue(repo, n):
    data = json.loads(run_gh("api", f"repos/{repo}/issues/{n}"))
    if "pull_request" in data:
        raise ValueError(f"#{n} is a pull request, not an issue")
    return {"state": data["state"].lower(), "assignees": [a["login"] for a in data.get("assignees", [])]}


def build_queue(repo, roles):
    tickets, issues, skipped = [], {}, []
    for issue in sorted(pages(f"repos/{repo}/issues?state=open&labels=ready-for-agent"), key=lambda i: i["number"]):
        if "pull_request" in issue:
            continue
        n = issue["number"]
        issues[n] = {"state": "open", "assignees": [a["login"] for a in issue.get("assignees") or []]}
        try:
            tickets.append(parse_ticket(n, issue.get("body"), roles))
        except ValueError as exc:
            skipped.append({"issue": n, "reason": str(exc)})
    return tickets, issues, skipped


def make_plan(members, tickets, issues):
    roster = {m["login"].casefold(): m for m in members}
    load = dict.fromkeys(roster, 0.0)
    owners = {n: list(issue["assignees"]) for n, issue in issues.items()}
    for ticket in tickets:
        for login in owners[ticket["number"]]:
            if login.casefold() in load:
                load[login.casefold()] += ticket["estimate"]
    result = []
    for ticket in tickets:
        n = ticket["number"]
        if owners[n]:
            result.append({"issue": n, "action": "skipped_assigned", "assignees": owners[n]})
            continue
        eligible = [m for m in members if ticket["role"] is None or ticket["role"] in m["roles"]]
        part_owners = {login.casefold() for p in ticket["parts"] for login in owners.get(p, [])}
        candidates = [m for m in eligible if m["login"].casefold() in part_owners] or eligible
        if not candidates:
            result.append({"issue": n, "action": "no_member_with_role", "role": ticket["role"]})
            continue
        chosen = min(candidates, key=lambda m: (load[m["login"].casefold()] / m["capacity"], m["login"].casefold()))
        result.append({"issue": n, "action": "planned", "assignee": chosen["login"]})
        load[chosen["login"].casefold()] += ticket["estimate"]
        owners[n] = [chosen["login"]]
    return result


def execute(repo, plan):
    failed = False
    for row in plan:
        if row["action"] != "planned":
            continue
        try:
            current = fetch_issue(repo, row["issue"])
            if current["state"] != "open" or current["assignees"]:
                row.update(action="skipped_changed", current=current)
                continue
            run_gh("issue", "edit", str(row["issue"]), "--repo", repo, "--add-assignee", row["assignee"])
            verified = fetch_issue(repo, row["issue"])
            if row["assignee"].casefold() not in [x.casefold() for x in verified["assignees"]]:
                raise RuntimeError("assignment could not be verified")
            if len(verified["assignees"]) != 1:
                row.update(action="conflict_after_write", current=verified)
                failed = True
            else:
                row.update(action="applied")
        except (ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
            row.update(action="failed", error=str(exc))
            try:
                row["current"] = fetch_issue(repo, row["issue"])
            except (ValueError, RuntimeError, KeyError, json.JSONDecodeError):
                row["current"] = "unavailable; inspect issue before retrying"
            failed = True
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="write assignments to GitHub")
    args = parser.parse_args()
    try:
        repo, roles, members = validate_team(json.loads(args.team.read_text(encoding="utf-8-sig")))
        env_repo = os.environ.get("GITHUB_REPOSITORY")
        if env_repo and env_repo.casefold() != repo.casefold():
            raise ValueError("roster repository does not match the GitHub Actions repository")
        tickets, issues, skipped = build_queue(repo, roles)
        for n in sorted({p for t in tickets for p in t["parts"]} - issues.keys()):
            try:
                issues[n] = fetch_issue(repo, n)
            except (ValueError, RuntimeError, KeyError, json.JSONDecodeError):
                issues[n] = {"state": "unknown", "assignees": []}  # a missing part only loses the owner preference
        plan = make_plan(members, tickets, issues)
        for login in sorted({row["assignee"] for row in plan if row["action"] == "planned"}):
            try:
                run_gh("api", f"repos/{repo}/assignees/{login}")
            except RuntimeError as exc:
                for row in plan:
                    if row["action"] == "planned" and row["assignee"] == login:
                        row.update(action="failed", error=f"{login} cannot be assigned in {repo}: {exc}")
        failed = execute(repo, plan) if args.apply else False
        print(json.dumps({"repository": repo, "mode": "apply" if args.apply else "preview", "results": plan, "skipped": skipped}, ensure_ascii=False, indent=2))
        return 1 if failed or any(row["action"] in ("skipped_changed", "conflict_after_write", "failed") for row in plan) else 0
    except (ValueError, TypeError, RuntimeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"Distribution stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
