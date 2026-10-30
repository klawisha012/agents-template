import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

script = Path(__file__).resolve().parents[1] / ".agents" / "workflow" / "availability.py"


class AvailabilityCommandTests(unittest.TestCase):
    def test_check_in_and_leave_update_only_the_selected_member(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "team.json"
            team = {"repository": "team/repo", "members": [{"login": "alice"}, {"login": "bob", "availability": {"state": "away"}}]}
            path.write_text(json.dumps(team), encoding="utf-8")
            subprocess.run([sys.executable, str(script), "--team", str(path), "--login", "alice", "--hours", "8"], check=True, capture_output=True)
            result = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result["members"][0]["availability"]["state"], "working")
            self.assertTrue(result["members"][0]["availability"]["until"].endswith("Z"))
            self.assertEqual(result["members"][1], team["members"][1])
            subprocess.run([sys.executable, str(script), "--team", str(path), "--login", "alice", "--away"], check=True, capture_output=True)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["members"][0]["availability"], {"state": "away"})


if __name__ == "__main__":
    unittest.main()
