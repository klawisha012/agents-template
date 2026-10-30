import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

script = Path(__file__).resolve().parents[1] / ".agents" / "workflow" / "availability.py"


class AvailabilityCommandTests(unittest.TestCase):
    def test_refuses_to_change_a_roster_for_another_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "team.json"
            original = json.dumps({"repository": "other/repo", "members": [{"login": "alice"}]})
            path.write_text(original, encoding="utf-8")
            env = {**os.environ, "GITHUB_REPOSITORY": "team/repo"}
            result = subprocess.run([sys.executable, str(script), "--team", str(path), "--login", "alice", "--away"], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_check_in_and_leave_update_only_the_selected_member(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "team.json"
            team = {"repository": "team/repo", "members": [{"login": "alice"}, {"login": "bob", "availability": {"state": "away"}}]}
            path.write_text(json.dumps(team), encoding="utf-8")
            env = {**os.environ, "GITHUB_REPOSITORY": "team/repo"}
            subprocess.run([sys.executable, str(script), "--team", str(path), "--login", "alice", "--hours", "8"], check=True, capture_output=True, env=env)
            result = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result["members"][0]["availability"]["state"], "working")
            self.assertTrue(result["members"][0]["availability"]["until"].endswith("Z"))
            self.assertEqual(result["members"][1], team["members"][1])
            subprocess.run([sys.executable, str(script), "--team", str(path), "--login", "alice", "--away"], check=True, capture_output=True, env=env)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["members"][0]["availability"], {"state": "away"})


if __name__ == "__main__":
    unittest.main()
