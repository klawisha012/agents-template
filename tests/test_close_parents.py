import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

directory = Path(__file__).resolve().parents[1] / ".agents" / "workflow"
sys.path.insert(0, str(directory))
spec = importlib.util.spec_from_file_location("close_parents", directory / "close_parents.py")
close_parents = importlib.util.module_from_spec(spec)
spec.loader.exec_module(close_parents)


def parent(n, total, completed, state="OPEN", repo="team/repo", labels=()):
    return {"number": n, "state": state, "repository": {"nameWithOwner": repo},
            "labels": {"nodes": [{"name": name} for name in labels]}, "subIssuesSummary": {"total": total, "completed": completed}}


def reply(value):
    return json.dumps({"data": {"repository": {"issue": {"parent": value}}}})


class CloseParentsTests(unittest.TestCase):
    def closes(self, *parents):
        replies = [reply(p) for p in parents]
        with patch.object(close_parents, "run_gh", side_effect=lambda *args: replies.pop(0) if args[0] == "api" else "") as gh:
            closed = close_parents.close_finished_parents("team/repo", 13)
        return closed, [c.args[2] for c in gh.call_args_list if c.args[0] == "issue"]

    def test_last_closed_ticket_closes_slice_and_then_spec(self):
        closed, writes = self.closes(parent(10, 3, 3), parent(2, 4, 4), None)
        self.assertEqual(closed, [10, 2])
        self.assertEqual(writes, ["10", "2"])

    def test_stops_at_parent_with_open_sub_issues(self):
        closed, writes = self.closes(parent(10, 3, 3), parent(2, 4, 3))
        self.assertEqual(closed, [10])
        self.assertEqual(writes, ["10"])

    def test_leaves_maps_other_repositories_and_closed_parents_alone(self):
        for skipped in (parent(10, 1, 1, labels=["wayfinder:map"]), parent(10, 1, 1, repo="other/repo"), parent(10, 1, 1, state="CLOSED"), None):
            self.assertEqual(self.closes(skipped), ([], []))


if __name__ == "__main__":
    unittest.main()
