import unittest


class TestProgressContracts(unittest.TestCase):
    def test_progress_is_none_or_within_0_1(self):
        from core.contracts.progress import normalize_progress

        self.assertIsNone(normalize_progress(None))
        self.assertEqual(normalize_progress(0.0), 0.0)
        self.assertEqual(normalize_progress(1.0), 1.0)

        with self.assertRaises(ValueError):
            normalize_progress(-0.01)
        with self.assertRaises(ValueError):
            normalize_progress(1.01)

    def test_stage_progress_is_monotonic_per_stage_best_effort(self):
        from core.contracts.progress import ProgressTracker
        from core.contracts.stages import PublicStage

        t = ProgressTracker()

        self.assertEqual(t.update(PublicStage.TRANSCRIBE, 0.2).progress, 0.2)
        # best-effort: do not go backwards
        self.assertEqual(t.update(PublicStage.TRANSCRIBE, 0.1).progress, 0.2)
        self.assertEqual(t.update(PublicStage.ANALYZE, 0.1).progress, 0.1)


if __name__ == "__main__":
    unittest.main()
