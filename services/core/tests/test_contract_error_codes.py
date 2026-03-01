import unittest


class TestErrorCodesRegistry(unittest.TestCase):
    def test_error_codes_include_minimum_required_set(self):
        from core.contracts.error_codes import ErrorCode

        required = {
            "VALIDATION_ERROR",
            "UNSUPPORTED_SOURCE_TYPE",
            "INVALID_SOURCE_URL",
            "PROJECT_NOT_FOUND",
            "JOB_NOT_FOUND",
            "ASSET_NOT_FOUND",
            "RESULT_NOT_FOUND",
            "FFMPEG_MISSING",
            "YTDLP_MISSING",
            "JOB_STAGE_FAILED",
            "JOB_CANCELED",
            "JOB_NOT_CANCELLABLE",
            "RESOURCE_EXHAUSTED",
            "UNAUTHORIZED",
            "FORBIDDEN",
            "PATH_TRAVERSAL_BLOCKED",
        }

        self.assertTrue(required.issubset({c.value for c in ErrorCode}))

    def test_error_envelope_uses_camel_case_request_id(self):
        from core.contracts.error_codes import ErrorCode
        from core.contracts.error_envelope import build_error_envelope

        payload = build_error_envelope(
            code=ErrorCode.JOB_NOT_FOUND,
            message="Job does not exist",
            details={"jobId": "b3b2..."},
            request_id="req_01J...",
        )

        self.assertIn("error", payload)
        self.assertIn("requestId", payload["error"])
        self.assertNotIn("request_id", payload["error"])


if __name__ == "__main__":
    unittest.main()
