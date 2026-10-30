import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / ".agents" / "workflow" / "distribute.py"
spec = importlib.util.spec_from_file_location("distribute", path)
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


def member(login, capacity=1, skills=None, availability=None):
    if availability is None:
        availability = {"state": "working", "until": "2099-01-01T00:00:00Z"}
    return {"login": login, "capacity": capacity, "skills": skills or [], "availability": availability}


def issue(n, blockers=None, skills=None, estimate=1):
    return {"number": n, "blocked_by": blockers or [], "skills": skills or [], "estimate": estimate}


def plan(members, tickets, data):
    _, people, ordered = distribution.validate({"repository": "team/repo", "members": members}, {"issues": tickets})
    return distribution.make_plan(people, ordered, data)


class DistributionTests(unittest.TestCase):
    def test_one_person_owns_all_and_dependency_stays_blocked(self):
        data = {n: {"state": "open", "assignees": []} for n in (1, 2)}
        result = plan([member("alice")], [issue(2, [1]), issue(1)], data)
        self.assertEqual([r["assignee"] for r in result], ["alice", "alice"])
        self.assertEqual(result[1]["open_blockers"], [1])
        self.assertFalse(result[1]["ready"])

    def test_many_people_and_weighted_capacity(self):
        data = {n: {"state": "open", "assignees": []} for n in range(1, 7)}
        result = plan([member("alice", 2), member("bob")], [issue(n) for n in data], data)
        self.assertEqual([r["assignee"] for r in result].count("alice"), 4)
        self.assertEqual([r["assignee"] for r in result].count("bob"), 2)
        members = [member("user" + str(n)) for n in range(100)]
        result = plan(members, [issue(1)], {1: data[1]})
        self.assertEqual(result[0]["action"], "planned")

    def test_skills_match_and_missing_skill_does_not_guess(self):
        data = {1: {"state": "open", "assignees": []}, 2: {"state": "open", "assignees": []}}
        result = plan([member("alice", skills=["frontend"]), member("bob", skills=["backend"])], [issue(1, skills=["backend"]), issue(2, skills=["security"])], data)
        self.assertEqual(result[0]["assignee"], "bob")
        self.assertEqual(result[1]["action"], "waiting_for_available")

    def test_existing_assignment_is_preserved_and_counted(self):
        data = {1: {"state": "open", "assignees": ["alice"]}, 2: {"state": "open", "assignees": []}}
        result = plan([member("alice"), member("bob")], [issue(1), issue(2)], data)
        self.assertEqual(result[0]["action"], "skipped_assigned")
        self.assertEqual(result[1]["assignee"], "bob")

    def test_external_closed_blocker_does_not_block(self):
        data = {1: {"state": "open", "assignees": []}, 99: {"state": "closed", "assignees": []}}
        result = plan([member("alice")], [issue(1, [99])], data)
        self.assertTrue(result[0]["ready"])

    def test_cycle_and_empty_roster_fail(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            distribution.validate({"repository": "team/repo", "members": [member("alice")]}, {"issues": [issue(1, [2]), issue(2, [1])]})
        with self.assertRaisesRegex(ValueError, "at least one"):
            distribution.validate({"repository": "team/repo", "members": []}, {"issues": [issue(1)]})

    def test_apply_rechecks_and_does_not_replace_new_owner(self):
        rows = [{"issue": 1, "action": "planned", "assignee": "alice"}]
        with patch.object(distribution, "fetch_issue", return_value={"state": "open", "assignees": ["bob"]}), patch.object(distribution, "run_gh") as gh:
            distribution.execute("team/repo", rows)
        self.assertEqual(rows[0]["action"], "skipped_changed")
        gh.assert_not_called()

    def test_apply_verifies_and_reports_failure(self):
        rows = [{"issue": 1, "action": "planned", "assignee": "alice"}]
        states = [{"state": "open", "assignees": []}, {"state": "open", "assignees": []}, {"state": "open", "assignees": []}]
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

    def test_away_owner_is_reassigned_to_working_skilled_member(self):
        people = [member("alice", skills=["backend"], availability={"state": "away"}), member("bob", skills=["backend"])]
        result = plan(people, [issue(1, skills=["backend"])], {1: {"state": "open", "assignees": ["alice"]}})
        self.assertEqual(result[0]["action"], "planned_reassign")
        self.assertEqual(result[0]["assignee"], "bob")
        self.assertEqual(result[0]["expected_assignees"], ["alice"])

    def test_no_available_recipient_preserves_existing_owner(self):
        people = [member("alice", skills=["backend"], availability={"state": "away"}), member("bob", skills=["frontend"])]
        result = plan(people, [issue(1, skills=["backend"]), issue(2, skills=["backend"])], {1: {"state": "open", "assignees": ["alice"]}, 2: {"state": "open", "assignees": []}})
        self.assertEqual([r["action"] for r in result], ["waiting_for_available", "waiting_for_available"])
        self.assertEqual(result[0]["assignees"], ["alice"])

    def test_missing_presence_is_not_available_or_authority_to_reassign(self):
        people = [member("bob"), {"login": "alice", "skills": []}]
        result = plan(people, [issue(1), issue(2)], {1: {"state": "open", "assignees": ["alice"]}, 2: {"state": "open", "assignees": []}})
        self.assertEqual(result[0]["action"], "skipped_assigned")
        self.assertEqual(result[1]["assignee"], "bob")

    def test_shift_expiry_and_explicit_timezone(self):
        now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(distribution.availability({"state": "working", "until": "2030-01-01T16:00:00+03:00"}, now)["available"])
        self.assertFalse(distribution.availability({"state": "working", "until": "2030-01-01T15:00:00+03:00"}, now)["available"])
        with self.assertRaisesRegex(ValueError, "timezone"):
            distribution.availability({"state": "working", "until": "2030-01-01T15:00:00"}, now)

    def test_reassignment_checks_owner_and_verifies(self):
        rows = [{"issue": 1, "action": "planned_reassign", "assignee": "bob", "expected_assignees": ["alice"]}]
        states = [{"state": "open", "assignees": ["alice"]}, {"state": "open", "assignees": ["bob"]}]
        with patch.object(distribution, "fetch_issue", side_effect=states), patch.object(distribution, "run_gh") as gh:
            failed = distribution.execute("team/repo", rows)
        self.assertFalse(failed)
        self.assertEqual(rows[0]["action"], "applied")
        gh.assert_called_once_with("issue", "edit", "1", "--repo", "team/repo", "--add-assignee", "bob", "--remove-assignee", "alice")

    def test_unknown_or_multiple_assignees_are_not_changed(self):
        people = [member("alice", availability={"state": "away"}), member("bob")]
        data = {1: {"state": "open", "assignees": ["outsider"]}, 2: {"state": "open", "assignees": ["alice", "outsider"]}}
        result = plan(people, [issue(1), issue(2)], data)
        self.assertEqual([r["action"] for r in result], ["skipped_assigned", "skipped_assigned"])

    def test_recipient_whose_shift_expired_before_write_is_skipped(self):
        rows = [{"issue": 1, "action": "planned", "assignee": "alice", "expected_assignees": []}]
        people = [{"login": "alice", "availability": {"until": "2020-01-01T00:00:00+00:00"}}]
        with patch.object(distribution, "run_gh") as gh, patch.object(distribution, "fetch_issue") as fetch:
            failed = distribution.execute("team/repo", rows, people)
        self.assertTrue(failed)
        self.assertEqual(rows[0]["action"], "skipped_expired")
        gh.assert_not_called()
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
