"""Exercise hosted requests without weakening the loopback server's checks."""

import os
import unittest

os.environ["RENDER_EXTERNAL_URL"] = "https://proofscope.example.com"

from hosted import app  # noqa: E402


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.origin = "https://proofscope.example.com"

    def test_assets_examples_and_valid_proof(self):
        for path in ("/", "/app.js", "/style.css"):
            self.assertEqual(self.client.get(path, base_url=self.origin).status_code, 200)
        examples = self.client.get("/api/examples", base_url=self.origin)
        self.assertTrue(examples.json)
        response = self.client.post(
            "/api/verify",
            base_url=self.origin,
            json={"source": "GIVEN a\nDERIVE a\nCONCLUDE"},
            headers={"Origin": self.origin},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("semantics", response.json)

    def test_foreign_origin_and_host_are_rejected(self):
        self.assertEqual(
            self.client.post(
                "/api/verify",
                base_url=self.origin,
                json={"source": ""},
                headers={"Origin": "https://foreign.example.com"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/", base_url="https://foreign.example.com").status_code, 400
        )

    def test_bad_and_oversized_input(self):
        self.assertEqual(
            self.client.post(
                "/api/verify",
                base_url=self.origin,
                json={"source": 12},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/verify",
                base_url=self.origin,
                json={"source": "x" * 65537},
            ).status_code,
            413,
        )
        self.assertEqual(
            self.client.post(
                "/api/verify",
                base_url=self.origin,
                data="x" * 300001,
                content_type="application/json",
            ).status_code,
            413,
        )
