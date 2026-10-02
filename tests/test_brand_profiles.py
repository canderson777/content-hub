import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from content_store import ContentStore
from server import create_server


BRANDS = ("brand-a", "brand-b", "brand-c")
PROFILE_FIELDS = {
    "voiceStyle",
    "audience",
    "offerAndLinks",
    "ctaStyle",
    "neverUse",
    "contentPillars",
    "positioning",
}


class BrandProfileApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_dir = self.root / "hub"
        self.project_dir.mkdir()
        (self.project_dir / "index.html").write_text("hub", encoding="utf-8")
        self.brands_root = self.root / "brands"
        self.db_path = self.root / "content-hub.sqlite3"
        self.source_snapshots = {}
        for brand_id in BRANDS:
            self._write_profile_sources(brand_id)
        self._start_server()

    def tearDown(self):
        self._stop_server()
        self.temp.cleanup()

    def _write_profile_sources(self, brand_id):
        brand_root = self.brands_root / brand_id
        positions = brand_root / "positions"
        positions.mkdir(parents=True, exist_ok=True)
        use_heading = "Words / phrases to use (pulled from existing materials)" if brand_id == "brand-c" else "Words / phrases to use"
        avoid_heading = "Words / phrases to avoid (explicit rules from source notes)" if brand_id == "brand-c" else "Words / phrases to avoid"
        files = {
            "brand-voice.md": (
                f"# Brand Voice\n\n## Voice summary\nVOICE {brand_id}\n\n"
                f"## {use_heading}\nUse WORDING-{brand_id}\n\n"
                f"## {avoid_heading}\nAvoid HYPE-{brand_id}\n\n"
                f"## CTA style\nCTA {brand_id}\n"
            ),
            "audience.md": f"# Audience\n\n## Primary audience\nAUDIENCE {brand_id}\n",
            "offers.md": f"# Offers\n\n## Main offer\nOFFER {brand_id}\n",
            "content-pillars.md": f"# Content Pillars\n\n## Pillar 1\nPILLAR {brand_id}\n",
            "positions/three-ps.md": f"# Three P's\n\n## Person\nPOSITION {brand_id}\n",
        }
        if brand_id == "brand-a":
            files["links-and-assets.md"] = f"# Links\n\nhttps://{brand_id}.example\n"
        for relative_path, content in files.items():
            path = brand_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.source_snapshots[path] = path.read_bytes()

    def _start_server(self):
        self.server = create_server(
            self.project_dir,
            self.brands_root,
            host="127.0.0.1",
            port=0,
            content_db_path=self.db_path,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def _stop_server(self):
        server = getattr(self, "server", None)
        if server is None:
            return
        server.shutdown()
        server.server_close()
        self.thread.join(timeout=2)
        self.server = None

    def _restart_server(self):
        self._stop_server()
        self._start_server()

    def request(self, method, path, payload=None, origin=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Origin": origin or f"http://{self.host}:{self.port}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw_body = response.read()
        content_type = response.getheader("Content-Type", "")
        result = response.status, json.loads(raw_body or b"{}") if "application/json" in content_type else raw_body.decode("utf-8", errors="replace")
        connection.close()
        return result

    def get_profile(self, brand_id):
        return self.request("GET", f"/api/brand-profile?brand={brand_id}")

    def test_source_profiles_are_returned_for_each_configured_brand(self):
        for brand_id in BRANDS:
            with self.subTest(brand=brand_id):
                status, payload = self.get_profile(brand_id)
                self.assertEqual(200, status)
                profile = payload["profile"]
                self.assertEqual(brand_id, profile["brandId"])
                self.assertEqual(PROFILE_FIELDS, set(profile["fields"]))
                self.assertIn(f"VOICE {brand_id}", profile["fields"]["voiceStyle"])
                self.assertIn(f"Use WORDING-{brand_id}", profile["fields"]["voiceStyle"])
                self.assertIn(f"AUDIENCE {brand_id}", profile["fields"]["audience"])
                self.assertIn(f"OFFER {brand_id}", profile["fields"]["offerAndLinks"])
                self.assertIn(f"CTA {brand_id}", profile["fields"]["ctaStyle"])
                self.assertIn(f"Avoid HYPE-{brand_id}", profile["fields"]["neverUse"])
                self.assertIn(f"PILLAR {brand_id}", profile["fields"]["contentPillars"])
                self.assertIn(f"POSITION {brand_id}", profile["fields"]["positioning"])
                self.assertFalse(profile["isCustomized"])
                self.assertTrue(profile["sourceFiles"])
                self.assertTrue(all(":" not in path and "\\" not in path for path in profile["sourceFiles"]))
        a_status, a_payload = self.get_profile("brand-a")
        self.assertEqual(200, a_status)
        self.assertIn("https://brand-a.example", a_payload["profile"]["fields"]["offerAndLinks"])

    def test_profile_override_is_per_brand_persistent_and_never_writes_source_markdown(self):
        status, baseline = self.get_profile("brand-a")
        self.assertEqual(200, status)
        fields = dict(baseline["profile"]["fields"])
        fields["voiceStyle"] = "Content Hub-only override for Brand A."

        status, saved = self.request("PUT", "/api/brand-profile?brand=brand-a", {"fields": fields})
        self.assertEqual(200, status)
        self.assertTrue(saved["profile"]["isCustomized"])
        self.assertEqual("Content Hub-only override for Brand A.", saved["profile"]["fields"]["voiceStyle"])

        self._restart_server()
        status, persisted = self.get_profile("brand-a")
        self.assertEqual(200, status)
        self.assertTrue(persisted["profile"]["isCustomized"])
        self.assertEqual("Content Hub-only override for Brand A.", persisted["profile"]["fields"]["voiceStyle"])

        status, other = self.get_profile("brand-c")
        self.assertEqual(200, status)
        self.assertFalse(other["profile"]["isCustomized"])
        self.assertIn("VOICE brand-c", other["profile"]["fields"]["voiceStyle"])
        for path, content in self.source_snapshots.items():
            self.assertEqual(content, path.read_bytes(), str(path))

    def test_reset_restores_current_source_profile(self):
        status, baseline = self.get_profile("brand-b")
        self.assertEqual(200, status)
        edited = dict(baseline["profile"]["fields"])
        edited["ctaStyle"] = "Temporary local override"
        status, _ = self.request("PUT", "/api/brand-profile?brand=brand-b", {"fields": edited})
        self.assertEqual(200, status)

        status, reset = self.request("DELETE", "/api/brand-profile?brand=brand-b")
        self.assertEqual(200, status)
        self.assertFalse(reset["profile"]["isCustomized"])
        self.assertIn("CTA brand-b", reset["profile"]["fields"]["ctaStyle"])

    def test_profile_api_rejects_unknown_brand_and_invalid_fields(self):
        status, payload = self.get_profile("not-a-brand")
        self.assertEqual(404, status)
        self.assertIsInstance(payload, dict)
        self.assertIn("brand", payload["error"].lower())

        status, baseline = self.get_profile("brand-a")
        self.assertEqual(200, status)
        fields = dict(baseline["profile"]["fields"])
        fields["unexpected"] = "not allowed"
        status, payload = self.request("PUT", "/api/brand-profile?brand=brand-a", {"fields": fields})
        self.assertEqual(400, status)
        self.assertIn("field", payload["error"].lower())

    def test_cross_origin_profile_write_is_rejected(self):
        status, baseline = self.get_profile("brand-a")
        self.assertEqual(200, status)
        fields = dict(baseline["profile"]["fields"])
        fields["voiceStyle"] = "Must not persist"
        status, _ = self.request(
            "PUT",
            "/api/brand-profile?brand=brand-a",
            {"fields": fields},
            origin="http://attacker.example",
        )
        self.assertEqual(403, status)
        status, unchanged = self.get_profile("brand-a")
        self.assertEqual(200, status)
        self.assertIn("VOICE brand-a", unchanged["profile"]["fields"]["voiceStyle"])

    def test_schema_upgrade_adds_profile_storage_without_dropping_existing_content(self):
        legacy_path = self.root / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        connection.execute("CREATE TABLE content_records (id TEXT PRIMARY KEY, brand_id TEXT, title TEXT, target_date TEXT, created_at TEXT)")
        connection.execute("INSERT INTO content_records (id, brand_id, title) VALUES ('existing-id', 'brand-a', 'Existing review record')")
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()

        store = ContentStore(legacy_path)
        try:
            version = store._connection.execute("PRAGMA user_version").fetchone()[0]
            profile_table = store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='brand_profiles'"
            ).fetchone()
            record = store._connection.execute("SELECT title FROM content_records WHERE id='existing-id'").fetchone()
            self.assertEqual(2, version)
            self.assertIsNotNone(profile_table)
            self.assertEqual("Existing review record", record[0])
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
