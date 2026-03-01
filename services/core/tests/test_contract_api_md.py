import unittest
from pathlib import Path


class TestApiMdContracts(unittest.TestCase):
    def _load_api_md(self) -> str:
        repo_root = Path(__file__).resolve().parents[3]
        return (repo_root / "docs" / "api.md").read_text(encoding="utf-8")

    def test_results_and_assets_endpoints_are_frozen(self):
        text = self._load_api_md()

        self.assertIn("GET /api/v1/projects/{projectId}/results/latest", text)
        self.assertIn("GET /api/v1/assets/{assetId}", text)
        self.assertIn("GET /api/v1/assets/{assetId}/content", text)

    def test_error_envelope_uses_camel_case_request_id(self):
        text = self._load_api_md()

        self.assertIn('"requestId"', text)
        self.assertNotIn('"request_id"', text)

    def test_stage_and_sse_schema_reference_standards(self):
        text = self._load_api_md()

        self.assertIn("_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md", text)


if __name__ == "__main__":
    unittest.main()
