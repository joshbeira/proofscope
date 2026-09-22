import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from proofscope.server import create_server


class CLITests(unittest.TestCase):
    def run_cli(self, *args, source=None):
        return subprocess.run(
            [sys.executable, "-m", "proofscope", *args],
            input=source,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            check=False,
        )

    def test_valid_stdin_json(self):
        result = self.run_cli(
            "check", "-", "--json", "--semantic", source="GIVEN A DERIVE A CONCLUDE"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)[0]
        self.assertTrue(data["valid"])
        self.assertTrue(data["semantics"]["entailed"])

    def test_invalid_exit_and_location(self):
        result = self.run_cli("check", "-", source="# comment\nDERIVE A\nCONCLUDE")
        self.assertEqual(result.returncode, 1)
        self.assertIn("-:3:1: E_GOAL", result.stdout)

    def test_missing_file_json(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli("check", str(Path(directory) / "missing.proof"), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stdout)[0])

    def test_batch_keeps_io_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.proof").write_text("DERIVE A CONCLUDE")
            result = self.run_cli("check", str(root / "missing"), str(root / "bad.proof"), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(json.loads(result.stdout)), 2)

    def test_entailment_exit_codes(self):
        for goal, expected in (("A IMP A", 0), ("A", 1)):
            self.assertEqual(self.run_cli("entails", goal).returncode, expected)
        result = self.run_cli("entails", "A AND B", "--max-atoms", "1", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "limit")

    def test_invalid_formula_json(self):
        result = self.run_cli("entails", "A AND", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "error")

    def test_rules_version_and_trace(self):
        self.assertIn("OR_CASES", self.run_cli("rules").stdout)
        self.assertIn("1.0.0", self.run_cli("--version").stdout)
        result = self.run_cli("check", "-", "--trace", source="GIVEN A DERIVE A CONCLUDE")
        self.assertEqual(result.returncode, 0)
        self.assertIn("[from 1]", result.stdout)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        connection.close()
        return status, payload, response_headers

    def test_assets_and_examples(self):
        for path in ("/", "/style.css", "/app.js", "/api/examples"):
            with self.subTest(path=path):
                status, body, headers = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertIn("Content-Security-Policy", headers)
        status, body, _ = self.request("GET", "/api/examples")
        self.assertEqual(len(json.loads(body)), 8)

    def test_verification_api(self):
        status, body, _ = self.request(
            "POST",
            "/api/verify",
            json.dumps({"source": "GIVEN A DERIVE A CONCLUDE"}),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["valid"])
        self.assertTrue(data["semantics"]["entailed"])

    def test_syntax_error_is_a_result(self):
        status, body, _ = self.request(
            "POST", "/api/verify", '{"source":"bad"}', {"Content-Type": "application/json"}
        )
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["syntax_valid"])

    def test_bad_payloads(self):
        for body in ("[]", '{"source":3}', "not json"):
            with self.subTest(body=body):
                self.assertEqual(
                    self.request("POST", "/api/verify", body, {"Content-Type": "application/json"})[
                        0
                    ],
                    400,
                )

    def test_rejects_cross_origin_requests(self):
        self.assertEqual(
            self.request("GET", "/", headers={"Origin": "https://example.com"})[0], 403
        )
        self.assertEqual(self.request("GET", "/", headers={"Host": "example.com"})[0], 403)

    def test_no_arbitrary_file_serving(self):
        self.assertEqual(self.request("GET", "/../../pyproject.toml")[0], 404)

    def test_request_limits_and_content_type(self):
        self.assertEqual(self.request("POST", "/api/verify", "text")[0], 415)
        self.assertEqual(
            self.request("POST", "/api/verify", "", {"Content-Type": "application/json"})[0], 413
        )
        self.assertEqual(self.request("POST", "/missing")[0], 404)
        self.assertEqual(
            self.request(
                "POST",
                "/api/verify",
                json.dumps({"source": "A" * 65537}),
                {"Content-Type": "application/json"},
            )[0],
            413,
        )

    def test_invalid_port(self):
        with self.assertRaises(ValueError):
            create_server(65536)


if __name__ == "__main__":
    unittest.main()
