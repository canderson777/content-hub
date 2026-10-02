import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from server import AssetError, AssetLibrary, create_server


class AssetLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.brands_root = Path(self.temp.name) / "brands"
        self.brand_assets = self.brands_root / "brand-a" / "assets"
        self.brand_assets.mkdir(parents=True)
        (self.brand_assets / "logos").mkdir()
        (self.brand_assets / "logos" / "mark.png").write_bytes(b"image")
        (self.brand_assets / "notes.docx").write_bytes(b"not a visual asset")
        self.store = AssetLibrary(self.brands_root)

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_supported_files_from_only_the_selected_brand_assets(self):
        results = self.store.list_assets("brand-a")
        self.assertEqual(["logos/mark.png"], [item["path"] for item in results])
        self.assertTrue(results[0]["url"].startswith("/brand-assets/brand-a/"))

    def test_upload_saves_file_under_selected_brand_and_category(self):
        saved = self.store.save_upload("brand-a", "logos", "new mark.png", b"new-image")
        destination = self.brand_assets / "logos" / "new mark.png"
        self.assertEqual(b"new-image", destination.read_bytes())
        self.assertEqual("logos/new mark.png", saved["path"])

    def test_source_review_assets_are_flagged_for_owner_review(self):
        review_dir = self.brand_assets / "social" / "post-images" / "source-review"
        review_dir.mkdir(parents=True)
        (review_dir / "needs-review.png").write_bytes(b"image")
        assets = self.store.list_assets("brand-a")
        review_asset = next(item for item in assets if item["name"] == "needs-review.png")
        self.assertTrue(review_asset["review_required"])

    def test_unused_assets_are_flagged_for_owner_review(self):
        unused_dir = self.brand_assets / "social" / "covers-banners" / "_unused"
        unused_dir.mkdir(parents=True)
        (unused_dir / "old-banner.jpg").write_bytes(b"image")
        assets = self.store.list_assets("brand-a")
        unused_asset = next(item for item in assets if item["name"] == "old-banner.jpg")
        self.assertTrue(unused_asset["review_required"])

    def test_upload_rejects_overwrite_and_path_traversal(self):
        with self.assertRaises(AssetError) as duplicate:
            self.store.save_upload("brand-a", "logos", "mark.png", b"replacement")
        self.assertEqual(409, duplicate.exception.status)
        with self.assertRaises(AssetError):
            self.store.save_upload("brand-a", "logos", "../outside.png", b"nope")

    def test_upload_rejects_unknown_brand_category_and_file_type(self):
        for args in [
            ("unknown", "logos", "a.png"),
            ("brand-a", "unknown", "a.png"),
            ("brand-a", "logos", "a.exe"),
        ]:
            with self.subTest(args=args), self.assertRaises(AssetError):
                self.store.save_upload(*args, b"data")


class AssetApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp.name) / "hub"
        self.project_dir.mkdir()
        (self.project_dir / "index.html").write_text("hub", encoding="utf-8")
        self.brands_root = Path(self.temp.name) / "brands"
        self.brand_assets = self.brands_root / "brand-a" / "assets" / "logos"
        self.brand_assets.mkdir(parents=True)
        self.server = create_server(self.project_dir, self.brands_root, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        result = response.status, response.getheaders(), payload
        connection.close()
        return result

    def test_brands_api_exposes_only_configured_brands(self):
        status, _, payload = self.request("GET", "/api/brands")
        data = json.loads(payload)
        self.assertEqual(200, status)
        self.assertEqual({"brand-a", "brand-b", "brand-c"}, {brand["id"] for brand in data["brands"]})

    def test_upload_api_writes_to_selected_brand_and_returns_it(self):
        status, _, payload = self.request(
            "POST",
            "/api/upload?brand=brand-a&category=logos&name=logo.png",
            body=b"uploaded-image",
            headers={"Content-Type": "image/png", "Origin": f"http://{self.host}:{self.port}"},
        )
        self.assertEqual(201, status)
        self.assertEqual(b"uploaded-image", (self.brand_assets / "logo.png").read_bytes())
        self.assertEqual("logos/logo.png", json.loads(payload)["asset"]["path"])

    def test_upload_api_rejects_cross_origin_requests(self):
        status, _, _ = self.request(
            "POST",
            "/api/upload?brand=brand-a&category=logos&name=logo.png",
            body=b"uploaded-image",
            headers={"Origin": "http://attacker.example"},
        )
        self.assertEqual(403, status)
        self.assertFalse((self.brand_assets / "logo.png").exists())

    def test_asset_route_serves_existing_file(self):
        (self.brand_assets / "existing.png").write_bytes(b"file-bytes")
        status, headers, body = self.request("GET", "/brand-assets/brand-a/logos/existing.png")
        self.assertEqual(200, status)
        self.assertEqual(b"file-bytes", body)
        self.assertIn(("Content-Type", "image/png"), headers)

    def test_asset_route_rejects_cross_site_browser_requests(self):
        (self.brand_assets / "private.png").write_bytes(b"private-file")
        status, _, _ = self.request(
            "GET",
            "/brand-assets/brand-a/logos/private.png",
            headers={"Sec-Fetch-Site": "cross-site", "Origin": "http://attacker.example"},
        )
        self.assertEqual(403, status)


class ContentApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp.name) / "hub"
        self.project_dir.mkdir()
        (self.project_dir / "index.html").write_text("hub", encoding="utf-8")
        self.brands_root = Path(self.temp.name) / "brands"
        self.db_path = Path(self.temp.name) / "content-hub.sqlite3"
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

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, payload=None, origin=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        headers = {"Origin": origin or f"http://{self.host}:{self.port}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read()
        try:
            payload = json.loads(response_body or b"{}")
        except json.JSONDecodeError:
            payload = {"body": response_body.decode("utf-8", errors="replace")}
        result = response.status, payload
        connection.close()
        return result

    def submit(self, brand_id="brand-c", target_date="2026-10-04"):
        return self.request("POST", "/api/content", {
            "brandId": brand_id,
            "title": "Review request follow-up",
            "contentType": "social",
            "channel": "linkedin",
            "format": "linkedin-post",
            "body": "A specific, editable draft body.",
            "brief": "Share a practical follow-up.",
            "sourceModule": "repurpose",
            "sourceId": "repurpose-local-1",
            "targetDate": target_date,
        })

    def action(self, record_id, action, **fields):
        return self.request("POST", f"/api/content/{record_id}/actions", {"action": action, **fields})

    def test_submitted_records_are_persisted_and_isolated_by_brand(self):
        status, local_record = self.submit("brand-c")
        self.assertEqual(201, status)
        self.assertEqual("Needs Review", local_record["record"]["status"])
        self.assertEqual("brand-c", local_record["record"]["brandId"])
        self.assertEqual("2026-10-04", local_record["record"]["targetDate"])
        _, other_record = self.submit("brand-b", None)
        self.assertEqual("brand-b", other_record["record"]["brandId"])

        status, local_list = self.request("GET", "/api/content?brand=brand-c")
        self.assertEqual(200, status)
        self.assertEqual([local_record["record"]["id"]], [item["id"] for item in local_list["records"]])
        status, other_list = self.request("GET", "/api/content?brand=brand-b")
        self.assertEqual(200, status)
        self.assertEqual([other_record["record"]["id"]], [item["id"] for item in other_list["records"]])

    def test_content_record_mutations_reject_cross_origin_requests(self):
        payload = {
            "brandId": "brand-c",
            "title": "Cross-site content",
            "contentType": "email",
            "channel": "email",
            "format": "email",
            "body": "This request must not create a record.",
        }
        for endpoint in ("/api/content", "/api/content/drafts"):
            status, response = self.request(
                "POST", endpoint, payload, origin="http://attacker.example"
            )
            self.assertEqual(403, status, response)
        _, listed = self.request("GET", "/api/content?brand=brand-c")
        self.assertEqual([], listed["records"])

    def test_localhost_and_127_0_0_1_interchangeable_origins_are_allowed(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/", headers={"Host": f"localhost:{self.port}", "Origin": f"http://127.0.0.1:{self.port}"})
        res = conn.getresponse()
        self.assertEqual(200, res.status)
        conn.close()

    def test_draft_editor_saves_by_brand_and_requires_explicit_review_submission(self):
        status, created = self.request("POST", "/api/content/drafts", {
            "brandId": "brand-c",
            "title": "Article working title",
            "contentType": "blog",
            "channel": "blog",
            "format": "article",
            "body": "First article draft.",
            "brief": "Help local owners solve a specific problem.",
            "targetDate": "2026-10-05",
        })
        self.assertEqual(201, status, created)
        record = created["record"]
        self.assertEqual("Draft", record["status"])
        self.assertEqual("brand-c", record["brandId"])
        self.assertEqual("2026-10-05", record["targetDate"])

        _, local_records = self.request("GET", "/api/content?brand=brand-c")
        _, other_records = self.request("GET", "/api/content?brand=brand-b")
        self.assertEqual([record["id"]], [item["id"] for item in local_records["records"]])
        self.assertEqual([], other_records["records"])

        status, saved = self.action(
            record["id"], "save_draft", title="Updated article title",
            body="Revised article draft.", brief="A more focused reader angle.", targetDate="2026-10-08",
        )
        self.assertEqual(200, status, saved)
        self.assertEqual("Draft", saved["record"]["status"])
        self.assertEqual("Updated article title", saved["record"]["title"])
        self.assertEqual("Revised article draft.", saved["record"]["body"])
        self.assertEqual("A more focused reader angle.", saved["record"]["brief"])
        self.assertEqual("2026-10-08", saved["record"]["targetDate"])

        status, _ = self.action(record["id"], "approve")
        self.assertEqual(409, status, "A draft must not be approved before review submission.")
        status, submitted = self.action(record["id"], "submit_for_review")
        self.assertEqual(200, status, submitted)
        self.assertEqual("Needs Review", submitted["record"]["status"])
        self.assertIsNone(submitted["record"]["scheduledAt"])

    def test_approve_edit_resubmit_and_skip_are_persistent_and_approval_does_not_schedule(self):
        _, submitted = self.submit(target_date=None)
        record_id = submitted["record"]["id"]

        status, approved = self.action(record_id, "approve")
        self.assertEqual(200, status)
        self.assertEqual("Approved", approved["record"]["status"])
        self.assertIsNone(approved["record"]["scheduledAt"])

        status, edited = self.action(
            record_id, "edit", body="Revised copy.", brief="Revised angle.", reviewNote="Add a concrete example."
        )
        self.assertEqual(200, status)
        self.assertEqual("Changes Requested", edited["record"]["status"])
        self.assertEqual("Revised copy.", edited["record"]["body"])
        self.assertEqual("Revised angle.", edited["record"]["brief"])

        status, resubmitted = self.action(record_id, "resubmit")
        self.assertEqual(200, status)
        self.assertEqual("Needs Review", resubmitted["record"]["status"])

        status, skipped = self.action(record_id, "skip")
        self.assertEqual(200, status)
        self.assertEqual("Skipped", skipped["record"]["status"])

        status, records = self.request("GET", "/api/content?brand=brand-c")
        self.assertEqual(200, status)
        self.assertEqual("Skipped", records["records"][0]["status"])
        self.assertEqual("Revised copy.", records["records"][0]["body"])

    def test_invalid_brand_date_and_status_transition_are_rejected(self):
        status, payload = self.submit("not-a-brand")
        self.assertEqual(400, status)
        self.assertIn("brand", payload["error"].lower())

        status, payload = self.submit("brand-c", "2026-02-30")
        self.assertEqual(400, status)
        self.assertIn("date", payload["error"].lower())

        _, submitted = self.submit(target_date=None)
        status, payload = self.action(submitted["record"]["id"], "confirm_published")
        self.assertEqual(409, status)
        self.assertIn("transition", payload["error"].lower())


if __name__ == "__main__":
    unittest.main()
