import unittest

from whorl.signal_loom_demo import build_demo


class SignalLoomDemoTests(unittest.TestCase):
    def test_demo_is_bounded_ranked_and_non_executing(self):
        result = build_demo()
        self.assertEqual(result["mode"], "offline_synthetic")
        self.assertEqual(result["interventions_executed"], 0)
        self.assertEqual(len(result["hotspots"]), 4)
        priorities = [item["priority"] for item in result["hotspots"]]
        self.assertEqual(priorities, sorted(priorities, reverse=True))
        self.assertEqual(len(result["events"]), 8)
        self.assertTrue(all(event["detail"]["demo"] for event in result["events"]))

    def test_demo_is_deterministic_except_timestamps(self):
        left = build_demo()
        right = build_demo()
        self.assertEqual(
            [(item["id"], item["priority"]) for item in left["hotspots"]],
            [(item["id"], item["priority"]) for item in right["hotspots"]],
        )
        self.assertEqual(
            [event["correlation_id"] for event in left["events"]],
            [event["correlation_id"] for event in right["events"]],
        )


if __name__ == "__main__":
    unittest.main()
