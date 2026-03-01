import unittest


class TestPublicStages(unittest.TestCase):
    def test_public_stage_enum_is_frozen(self):
        # RED: this import should fail until the contract module exists.
        from core.contracts.stages import PublicStage

        self.assertEqual(
            [s.value for s in PublicStage],
            [
                "ingest",
                "transcribe",
                "analyze",
                "assemble_result",
                "extract_keyframes",
            ],
        )

    def test_internal_to_public_mapping_is_defined(self):
        from core.contracts.stages import INTERNAL_STAGE_TO_PUBLIC_STAGE, PublicStage, to_public_stage

        self.assertEqual(INTERNAL_STAGE_TO_PUBLIC_STAGE["download"], PublicStage.INGEST)
        self.assertEqual(INTERNAL_STAGE_TO_PUBLIC_STAGE["plan"], PublicStage.ANALYZE)
        self.assertEqual(to_public_stage("ingest:download"), PublicStage.INGEST)
        self.assertEqual(to_public_stage("keyframes"), PublicStage.EXTRACT_KEYFRAMES)


if __name__ == "__main__":
    unittest.main()
