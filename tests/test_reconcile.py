import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

directory = Path(__file__).resolve().parents[1] / ".agents" / "workflow"
sys.path.insert(0, str(directory))
spec = importlib.util.spec_from_file_location("reconcile", directory / "reconcile.py")
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


class ReconciliationTests(unittest.TestCase):
    def test_uses_metadata_and_native_dependencies(self):
        issues = [{"number": 7, "body": '<!-- agent-distribution: {"skills":["backend"],"estimate":2,"blocked_by":[3]} -->'}]
        dependency = {"number": 4, "repository_url": "https://api.github.com/repos/team/repo"}
        with patch.object(reconcile, "pages", side_effect=[issues, [dependency]]):
            batch, skipped = reconcile.build_batch("team/repo")
        self.assertEqual(skipped, [])
        self.assertEqual(batch[0]["skills"], ["backend"])
        self.assertEqual(set(batch[0]["blocked_by"]), {3, 4})

    def test_missing_metadata_and_cross_repository_blockers_are_skipped(self):
        issues = [
            {"number": 1, "body": "no metadata"},
            {"number": 2, "body": '<!-- agent-distribution: {"skills":[],"estimate":1,"blocked_by":[]} -->'},
        ]
        other_repo = {"number": 4, "repository_url": "https://api.github.com/repos/other/repo"}
        with patch.object(reconcile, "pages", side_effect=[issues, [other_repo]]):
            batch, skipped = reconcile.build_batch("team/repo")
        self.assertEqual(batch, [])
        self.assertEqual([item["issue"] for item in skipped], [1, 2])

    def test_issue_pagination_reaches_next_page(self):
        first = [{"number": n} for n in range(100)]
        with patch.object(reconcile, "run_gh", side_effect=[json.dumps(first), '[{"number": 100}]']) as gh:
            data = reconcile.pages("repos/team/repo/issues?state=open")
        self.assertEqual(len(data), 101)
        self.assertIn("page=2", gh.call_args_list[1].args[1])

    def test_action_refuses_roster_for_another_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "team.json"
            path.write_text(json.dumps({"repository": "other/repo", "members": []}), encoding="utf-8")
            with patch.object(sys, "argv", ["reconcile.py", "--team", str(path), "--apply"]), patch.dict("os.environ", {"GITHUB_REPOSITORY": "team/repo"}), patch.object(reconcile, "run_gh") as gh:
                result = reconcile.main()
        self.assertEqual(result, 2)
        gh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
