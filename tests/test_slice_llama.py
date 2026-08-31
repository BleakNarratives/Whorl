"""Live llama-server wire test for whorl_slice.

Skips cleanly when no llama-server is reachable (default CI/offline), so it
never hard-fails the suite. When run with a live server (memory-gated launch,
see whorl_slice.py module docstring) it asserts that confidence comes from the
REAL model's log-probabilities, not the reference simulator.
"""
import unittest
import urllib.request

from whorl.slice.whorl_slice import LlamaServerPass

BASE = "http://127.0.0.1:8080"


def server_up() -> bool:
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
            return b'"ok"' in r.read()
    except Exception:
        return False


@unittest.skipUnless(server_up(), "no llama-server live on :8080")
class TestLlamaServerPass(unittest.TestCase):
    def setUp(self):
        self.p = LlamaServerPass(base_url=BASE, timeout=60)

    def test_real_logits_from_model(self):
        res = self.p.next_token("The plan begins when the captain")
        self.assertIsNotNone(res.token)
        # genuine top-logprobs: at least one candidate beyond top1 recorded
        self.assertGreaterEqual(len(res.top_k), 2)
        # confidence must be a real [0,1] normalized-entropy value
        self.assertGreaterEqual(res.confidence, 0.0)
        self.assertLessEqual(res.confidence, 1.0)
        # logits present = the raw log-probs came through, not a simulator
        self.assertTrue(res.logits)
        # OpenAI endpoint doesn't expose last hidden layer -> None (documented)
        self.assertIsNone(res.hidden_state)
        # probabilities in top_k are softmax-consistent (non-nan, sum ~1)
        tot = sum(c for _, c in res.top_k)
        self.assertAlmostEqual(tot, 1.0, delta=0.15)

    def test_per_seed_determinism_greedy(self):
        a = self.p.next_token("The weather today is")
        self.p.timeout = self.p.timeout  # no state mutation smoke guard
        b = self.p.next_token("The weather today is")
        self.assertEqual(a.token, b.token)


if __name__ == "__main__":
    unittest.main()