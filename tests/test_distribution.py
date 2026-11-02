import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / ".agents" / "workflow" / "distribute.py"
spec = importlib.util.spec_from_file_location("distribute", path)
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)

ROLES = {"frontend": "UI", "backend": "API"}


def team(*members, roles=ROLES):
    return {"repository": "team/repo", "roles": roles, "members": list(members)}


def member(login, roles=(), capacity=1):
    return {"login": login, "capacity": capacity, "roles": list(roles)}


def ticket(n, role=None, estimate=1, parts=()):
    return {"number": n, "role": role, "estimate": estimate, "parts": list(parts)}


def plan(members, tickets, owners=None, closed=None):
    _, _, people = distribution.validate_team(team(*members))
    owners = owners or {}
    issues = {t["number"]: {"state": "open", "assignees": owners.get(t["number"], [])} for t in tickets}
    issues.update({n: {"state": "closed", "assignees": a} for n, a in (closed or {}).items()})
    return distribution.make_plan(people, tickets, issues)


def body(metadata):
    return f"Text\n<!-- agent-distribution: {json.dumps(metadata)} -->"


class PlanTests(unittest.TestCase):
    def test_role_decides_who_can_take_a_ticket(self):
        result = plan([member("alice", ["frontend"]), member("bob", ["backend"])], [ticket(1, "backend"), ticket(2, "frontend"), ticket(3)])
        self.assertEqual([r["assignee"] for r in result], ["bob", "alice", "alice"])

    def test_capacity_weights_load(self):
        result = plan([member("alice", capacity=2), member("bob")], [ticket(n) for n in range(1, 7)])
        self.assertEqual([r["assignee"] for r in result].count("alice"), 4)
        self.assertEqual([r["assignee"] for r in result].count("bob"), 2)

    def test_role_nobody_has_leaves_ticket_unassigned(self):
        result = plan([member("bob", ["backend"])], [ticket(1, "frontend")])
        self.assertEqual(result[0]["action"], "no_member_with_role")

    def test_assigned_ticket_is_never_changed_but_counts_as_load(self):
        owners = {1: ["alice"], 2: ["outsider"], 3: ["alice", "bob"]}
        result = plan([member("alice"), member("bob")], [ticket(1, estimate=3), ticket(2), ticket(3), ticket(4)], owners)
        self.assertEqual([r["action"] for r in result[:3]], ["skipped_assigned"] * 3)
        self.assertEqual(result[3]["assignee"], "bob")

    def test_verification_ticket_prefers_owner_of_a_part_planned_in_the_same_run(self):
        people = [member("alice", ["frontend"]), member("bob", ["backend"]), member("carol")]
        result = plan(people, [ticket(1, "backend"), ticket(2, "frontend"), ticket(3, parts=[1, 2])])
        self.assertEqual([r["assignee"] for r in result], ["bob", "alice", "alice"])

    def test_verification_ticket_uses_closed_parts_and_falls_back_without_part_owners(self):
        people = [member("bob", ["backend"]), member("carol")]
        result = plan(people, [ticket(3, parts=[1]), ticket(4, parts=[2])], closed={1: ["bob"], 2: ["outsider"]})
        self.assertEqual([r["assignee"] for r in result], ["bob", "carol"])


class ValidationTests(unittest.TestCase):
    def test_roster_rejects_unknown_roles_old_fields_and_placeholders(self):
        cases = [
            (team(member("alice", ["design"])), "missing from team.roles"),
            (team({"login": "alice", "skills": ["general"]}), "replaced by roles"),
            (team({"login": "alice", "availability": {"state": "away"}}), "no longer used"),
            (team(member("alice"), roles={"frontend": ""}), "non-empty description"),
            (team(), "at least one"),
            ({"repository": "OWNER/REPOSITORY", "roles": {}, "members": [member("alice")]}, "actual"),
        ]
        for data, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                distribution.validate_team(data)

    def test_metadata_needs_one_known_role_or_null(self):
        roles = {"backend"}
        self.assertEqual(distribution.parse_ticket(7, body({"role": "Backend", "estimate": 2}), roles), ticket(7, "backend", 2.0))
        self.assertEqual(distribution.parse_ticket(8, body({"role": None, "parts": [2, 1]}), roles), ticket(8, None, 1.0, [1, 2]))
        cases = [
            ("no metadata", "missing"),
            (body({"role": None}) + body({"role": None}), "ambiguous"),
            (body({"skills": ["backend"], "estimate": 1}), "needs \"role\""),
            (body({"role": "design"}), "unknown role"),
            (body({"role": "backend", "parts": [1]}), "role null"),
            (body({"role": None, "estimate": 0}), "positive"),
        ]
        for text, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                distribution.parse_ticket(9, text, roles)


class GitHubTests(unittest.TestCase):
    def test_queue_is_sorted_and_skips_invalid_tickets_and_pull_requests(self):
        raw = [
            {"number": 5, "body": body({"role": None}), "assignees": [{"login": "alice"}]},
            {"number": 3, "body": body({"role": None}), "pull_request": {}},
            {"number": 2, "body": "no metadata", "assignees": []},
            {"number": 1, "body": body({"role": "backend"}), "assignees": []},
        ]
        with patch.object(distribution, "pages", return_value=raw):
            tickets, issues, skipped = distribution.build_queue("team/repo", {"backend"})
        self.assertEqual([t["number"] for t in tickets], [1, 5])
        self.assertEqual([s["issue"] for s in skipped], [2])
        self.assertEqual(issues[5]["assignees"], ["alice"])

    def test_issue_pagination_reaches_next_page(self):
        first = [{"number": n} for n in range(100)]
        with patch.object(distribution, "run_gh", side_effect=[json.dumps(first), '[{"number": 100}]']) as gh:
            data = distribution.pages("repos/team/repo/issues?state=open")
        self.assertEqual(len(data), 101)
        self.assertIn("page=2", gh.call_args_list[1].args[1])

    def test_apply_rechecks_and_does_not_replace_new_owner(self):
        rows = [{"issue": 1, "action": "planned", "assignee": "alice"}]
        with patch.object(distribution, "fetch_issue", return_value={"state": "open", "assignees": ["bob"]}), patch.object(distribution, "run_gh") as gh:
            distribution.execute("team/repo", rows)
        self.assertEqual(rows[0]["action"], "skipped_changed")
        gh.assert_not_called()

    def test_apply_verifies_and_reports_failure(self):
        rows = [{"issue": 1, "action": "planned", "assignee": "alice"}]
        states = [{"state": "open", "assignees": []}] * 3
        with patch.object(distribution, "fetch_issue", side_effect=states), patch.object(distribution, "run_gh"):
            failed = distribution.execute("team/repo", rows)
        self.assertTrue(failed)
        self.assertEqual(rows[0]["action"], "failed")

    def test_apply_writes_only_new_assignment_and_verifies(self):
        rows = [{"issue": 1, "action": "planned", "assignee": "alice"}]
        states = [{"state": "open", "assignees": []}, {"state": "open", "assignees": ["alice"]}]
        with patch.object(distribution, "fetch_issue", side_effect=states), patch.object(distribution, "run_gh") as gh:
            failed = distribution.execute("team/repo", rows)
        self.assertFalse(failed)
        self.assertEqual(rows[0]["action"], "applied")
        gh.assert_called_once_with("issue", "edit", "1", "--repo", "team/repo", "--add-assignee", "alice")

    def run_main(self, data, *args):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "team.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            output = io.StringIO()
            with patch.object(sys, "argv", ["distribute.py", "--team", str(path), *args]), \
                 patch.dict("os.environ", {"GITHUB_REPOSITORY": "team/repo"}), contextlib.redirect_stdout(output):
                return distribution.main(), output.getvalue()

    def test_refuses_roster_for_another_repository(self):
        data = team(member("alice"))
        data["repository"] = "other/repo"
        with patch.object(distribution, "run_gh") as gh:
            result, _ = self.run_main(data, "--apply")
        self.assertEqual(result, 2)
        gh.assert_not_called()

    def test_unassignable_login_fails_only_its_tickets(self):
        raw = [
            {"number": 1, "body": body({"role": "frontend"}), "assignees": []},
            {"number": 2, "body": body({"role": "backend"}), "assignees": []},
        ]

        def gh(*args):
            if args[:2] == ("api", "repos/team/repo/assignees/alice"):
                raise RuntimeError("HTTP 404")
            return ""

        states = [{"state": "open", "assignees": []}, {"state": "open", "assignees": ["bob"]}]
        with patch.object(distribution, "pages", return_value=raw), patch.object(distribution, "fetch_issue", side_effect=states), \
             patch.object(distribution, "run_gh", side_effect=gh):
            result, output = self.run_main(team(member("alice", ["frontend"]), member("bob", ["backend"])), "--apply")
        self.assertEqual(result, 1)
        self.assertEqual([r["action"] for r in json.loads(output)["results"]], ["failed", "applied"])

    def test_published_slice_gets_role_owners_and_verification_owner(self):
        raw = [
            {"number": 11, "body": body({"role": "backend", "estimate": 2}), "assignees": []},
            {"number": 12, "body": body({"role": "frontend"}), "assignees": []},
            {"number": 13, "body": body({"role": None, "parts": [11, 12]}), "assignees": []},
        ]
        unassigned = {"state": "open", "assignees": []}
        states = [unassigned, {"state": "open", "assignees": ["bob"]}, unassigned, {"state": "open", "assignees": ["alice"]}, unassigned, {"state": "open", "assignees": ["alice"]}]
        with patch.object(distribution, "pages", return_value=raw), patch.object(distribution, "fetch_issue", side_effect=states), \
             patch.object(distribution, "run_gh") as gh:
            result, output = self.run_main(team(member("alice", ["frontend"]), member("bob", ["backend"]), member("carol")), "--apply")
        self.assertEqual(result, 0)
        self.assertEqual([r["action"] for r in json.loads(output)["results"]], ["applied"] * 3)
        edits = [c.args for c in gh.call_args_list if c.args[0] == "issue"]
        self.assertEqual([(a[2], a[-1]) for a in edits], [("11", "bob"), ("12", "alice"), ("13", "alice")])


if __name__ == "__main__":
    unittest.main()
