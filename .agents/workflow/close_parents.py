#!/usr/bin/env python3
"""Close each parent issue, walking up from a closed issue, once all its sub-issues are closed."""
import argparse
import json
import os
import sys

from distribute import REPOSITORY, number, run_gh

QUERY = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      parent { number state repository { nameWithOwner } labels(first: 50) { nodes { name } } subIssuesSummary { total completed } }
    }
  }
}"""


def parent_of(repo, number):
    owner, name = repo.split("/")
    data = json.loads(run_gh("api", "graphql", "-f", f"query={QUERY}", "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"number={number}"))
    return data["data"]["repository"]["issue"]["parent"]


def finished(parent, repo):
    # A wayfinder map gains children as it is explored, so only its driver closes it.
    return (parent is not None and parent["state"] == "OPEN"
            and parent["repository"]["nameWithOwner"].casefold() == repo.casefold()
            and "wayfinder:map" not in [label["name"] for label in parent["labels"]["nodes"]]
            and parent["subIssuesSummary"]["completed"] == parent["subIssuesSummary"]["total"])


def close_finished_parents(repo, number):
    closed = []
    parent = parent_of(repo, number)
    # Closes made with GITHUB_TOKEN trigger no workflow, so the walk up the chain happens here.
    while finished(parent, repo):
        n = parent["number"]
        run_gh("issue", "close", str(n), "--repo", repo, "--reason", "completed", "--comment", "All sub-issues are closed.")
        closed.append(n)
        parent = parent_of(repo, n)
    return closed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, required=True, help="the issue that was just closed")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args()
    if not args.repo or not REPOSITORY.fullmatch(args.repo):
        parser.error("--repo must be OWNER/REPOSITORY")
    try:
        print(json.dumps({"repository": args.repo, "closed_parents": close_finished_parents(args.repo, number(args.issue, "--issue"))}))
        return 0
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f"Closing parents stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
