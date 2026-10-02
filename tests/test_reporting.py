import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from reporting import (
    GscClient,
    GscError,
    SOURCE_REGISTRY,
    default_gsc_token_path,
)
from server import create_server


class FakeGscClient:
    """Read-only GSC stand-in for endpoint tests; no network and no real token."""

    def __init__(self, sites=None, baseline=None, error=None):
        self.sites = sites or []
        self.baseline = baseline if baseline is not None else []
        self.error = error

    def list_sites(self):
        if self.error:
            raise self.error
        return self.sites

    def search_analytics(self, site_url, start_date, end_date):
        if self.error:
            raise self.error
        return self.baseline


class ReportingRegistryTests(unittest.TestCase):
    def test_registry_covers_the_three_selector_brands(self):
        self.assertEqual({"brand-a", "brand-c", "brand-b"}, set(SOURCE_REGISTRY))

    def test_brand_a_has_verified_gsc_property(self):
        sources = SOURCE_REGISTRY["brand-a"]
        gsc = next(source for source in sources if source["kind"] == "gsc")
        self.assertEqual("verified", gsc["status"])
        self.assertEqual("https://www.brand-a.example.com/", gsc["property"])
        self.assertEqual("siteOwner", gsc["permission"])

    def test_brand_c_has_verified_gsc_property_from_probe(self):
        sources = SOURCE_REGISTRY["brand-c"]
        gsc = next(source for source in sources if source["kind"] == "gsc")
        self.assertEqual("verified", gsc["status"])
        self.assertEqual("https://www.brand-c.example.com/", gsc["property"])
        self.assertEqual("siteOwner", gsc["permission"])

    def test_brand_b_has_no_verified_or_live_sources(self):
        for source in SOURCE_REGISTRY["brand-b"]:
            self.assertIn(source["status"], {"not_connected", "account_available"}, source)
            self.assertNotEqual("verified", source["status"])
        self.assertTrue(SOURCE_REGISTRY["brand-b"])

    def test_social_and_site_sources_are_listed_as_available_not_verified(self):
        a_kinds = {source["kind"] for source in SOURCE_REGISTRY["brand-a"]}
        self.assertTrue({"gsc", "social", "site"} <= a_kinds)
        social = next(source for source in SOURCE_REGISTRY["brand-a"] if source["kind"] == "social")
        self.assertIn(social["status"], {"account_available", "not_connected"})
        self.assertTrue(any(source["kind"] == "newsletter" for source in SOURCE_REGISTRY["brand-a"]))


class GscReportingEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp.name) / "hub"
        self.project_dir.mkdir()
        (self.project_dir / "index.html").write_text("hub", encoding="utf-8")
        self.brands_root = Path(self.temp.name) / "brands"
        self.db_path = Path(self.temp.name) / "content-hub.sqlite3"

    def build_server(self, gsc_client=None):
        server = create_server(
            self.project_dir,
            self.brands_root,
            host="127.0.0.1",
            port=0,
            content_db_path=self.db_path,
            gsc_client=gsc_client,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.host, self.port = server.server_address
        self.thread = thread
        return server

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        connection.request("GET", path, headers={"Origin": f"http://{self.host}:{self.port}"})
        response = connection.getresponse()
        body = json.loads(response.read() or b"{}")
        connection.close()
        return response.status, body

    def test_sources_endpoint_returns_honest_inventory_without_network(self):
        self.server = self.build_server()
        status, body = self.request("/api/reporting/sources")
        self.assertEqual(200, status)
        self.assertEqual({"brand-a", "brand-c", "brand-b"}, set(body["sources"]))
        for brand_sources in body["sources"].values():
            for source in brand_sources:
                self.assertIn("status", source)
                self.assertIn("kind", source)
                self.assertIn("description", source)

    def test_gsc_endpoint_returns_baseline_for_verified_brand(self):
        fake = FakeGscClient(
            sites=[{"siteUrl": "https://www.brand-a.example.com/", "permissionLevel": "siteOwner"}],
            baseline=[{"clicks": 12, "impressions": 340, "ctr": 0.035, "averagePosition": 9.4}],
        )
        self.server = self.build_server(gsc_client=fake)
        status, body = self.request("/api/reporting/gsc?brand=brand-a")
        self.assertEqual(200, status)
        self.assertEqual("https://www.brand-a.example.com/", body["property"])
        self.assertEqual("siteOwner", body["permission"])
        self.assertEqual(12, body["metrics"]["clicks"])
        self.assertEqual(340, body["metrics"]["impressions"])
        self.assertEqual(9.4, body["metrics"]["averagePosition"])
        self.assertIn("startDate", body["window"])
        self.assertIn("endDate", body["window"])
        self.assertNotIn("token", body)
        self.assertNotIn("access", body)

    def test_gsc_endpoint_rejects_unknown_brand(self):
        self.server = self.build_server(gsc_client=FakeGscClient())
        status, body = self.request("/api/reporting/gsc?brand=not-a-brand")
        self.assertEqual(404, status)

    def test_gsc_endpoint_returns_honest_state_for_brand_b_without_token(self):
        # Brand B has no GSC property; there must be no credential requirement,
        # and no fabricated figures.
        self.server = self.build_server(gsc_client=None)
        status, body = self.request("/api/reporting/gsc?brand=brand-b")
        self.assertEqual(404, status)
        self.assertIn("not connected", body.get("error", "").lower())

    def test_gsc_endpoint_reports_failed_provider_check_read_only(self):
        class ProviderFailure(Exception):
            pass

        self.server = self.build_server(
            gsc_client=FakeGscClient(error=ProviderFailure("provider unavailable"))
        )
        status, body = self.request("/api/reporting/gsc?brand=brand-a")
        self.assertEqual(502, status)
        self.assertIn("unavailable", body.get("error", "").lower())


class GscTokenPathTests(unittest.TestCase):
    def test_default_token_path_does_not_expose_token_values(self):
        path = default_gsc_token_path()
        self.assertIn("google_gsc_token.json", str(path))


class GscClientExpiryTests(unittest.TestCase):
    def _client_with_token(self, token_value):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        token_path = Path(tmp.name) / "google_gsc_token.json"
        token_path.write_text(token_value, encoding="utf-8")
        return GscClient(token_path)

    def test_naive_future_expiry_is_treated_as_utc_and_token_is_used(self):
        import datetime as dt

        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
        client = self._client_with_token(json.dumps({
            "token": "abc123",
            "scopes": ["https://www.googleapis.com/auth/webmasters.readonly"],
            "expiry": future,
        }))
        # No network: access token comes straight from the file.
        self.assertEqual(client._access_token(), "abc123")

    def test_naive_expired_expiry_triggers_refresh_instead_of_crashing(self):
        import datetime as dt
        from unittest import mock

        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()
        client = self._client_with_token(json.dumps({
            "token": "stale",
            "refresh_token": "rt",
            "client_id": "cid",
            "client_secret": "cs",
            "scopes": ["https://www.googleapis.com/auth/webmasters.readonly"],
            "expiry": past,
        }))
        with mock.patch("reporting.requests.post") as post:
            post.return_value.status_code = 400
            with self.assertRaises(GscError) as ctx:
                client._access_token()
            self.assertEqual(ctx.exception.status, 503)
            self.assertNotIn("naive", str(ctx.exception).lower())


class SourceMetaReportingTests(unittest.TestCase):
    """Registry now carries PageSpeed + MailerLite sources with honest statuses."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp.name) / "hub"
        self.project_dir.mkdir()
        (self.project_dir / "index.html").write_text("hub", encoding="utf-8")
        self.brands_root = Path(self.temp.name) / "brands"
        self.db_path = Path(self.temp.name) / "content-hub.sqlite3"

    def build_server(self, gsc_client=None, pagespeed_client=None, mailerlite_client=None):
        server = create_server(
            self.project_dir,
            self.brands_root,
            host="127.0.0.1",
            port=0,
            content_db_path=self.db_path,
            gsc_client=gsc_client,
            pagespeed_client=pagespeed_client,
            mailerlite_client=mailerlite_client,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.host, self.port = server.server_address
        self.thread = thread
        return server

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=3)
        connection.request("GET", path, headers={"Origin": f"http://{self.host}:{self.port}"})
        response = connection.getresponse()
        body = json.loads(response.read() or b"{}")
        connection.close()
        return response.status, body

    def test_registry_has_pagespeed_and_mailerlite_sources(self):
        self.server = self.build_server()
        status, body = self.request("/api/reporting/sources")
        self.assertEqual(200, status)
        a_kinds = {source["kind"] for source in body["sources"]["brand-a"]}
        lgu_kinds = {source["kind"] for source in body["sources"]["brand-c"]}
        self.assertIn("pagespeed", a_kinds)
        self.assertIn("pagespeed", lgu_kinds)
        self.assertIn("newsletter", a_kinds)

    def test_pagespeed_endpoint_returns_scores_for_verified_site(self):
        class FakePageSpeed:
            def run(self, url, strategy="mobile"):
                return {
                    "scores": {
                        "performance": 87,
                        "accessibility": 94,
                        "best-practices": 100,
                        "seo": 97,
                    },
                    "fetchTime": "2026-09-28T00:00:00Z",
                }

        self.server = self.build_server(pagespeed_client=FakePageSpeed())
        status, body = self.request("/api/reporting/pagespeed?brand=brand-a")
        self.assertEqual(200, status)
        self.assertEqual(87, body["scores"]["performance"])
        self.assertEqual(94, body["scores"]["accessibility"])
        self.assertIn("url", body)
        self.assertIn("fetchTime", body)

    def test_pagespeed_endpoint_honest_when_rate_limited(self):
        class RateLimited:
            def run(self, url, strategy="mobile"):
                raise GscError("PageSpeed quota exceeded.", 429)

        self.server = self.build_server(pagespeed_client=RateLimited())
        status, body = self.request("/api/reporting/pagespeed?brand=brand-a")
        self.assertEqual(429, status)
        self.assertIn("quota", body.get("error", "").lower())
        self.assertNotIn("scores", body)

    def test_pagespeed_endpoint_honest_for_unconnected_brand(self):
        self.server = self.build_server()
        status, body = self.request("/api/reporting/pagespeed?brand=brand-b")
        self.assertEqual(404, status)

    def test_mailerlite_endpoint_returns_group_stats(self):
        class FakeMailerLite:
            def list_groups(self):
                return [{
                    "id": "g1",
                    "name": "Brand A Newsletter",
                    "active_count": 16,
                    "sent_count": 1028,
                    "opens_count": 163,
                    "clicks_count": 15,
                    "open_rate": 0.1586,
                    "click_rate": 0.0146,
                    "unsubscribed_count": 4,
                }]

        self.server = self.build_server(mailerlite_client=FakeMailerLite())
        status, body = self.request("/api/reporting/mailerlite?brand=brand-a")
        self.assertEqual(200, status)
        self.assertEqual("Brand A Newsletter", body["groups"][0]["name"])
        self.assertEqual(1028, body["groups"][0]["sent_count"])
        self.assertNotIn("token", body)
        self.assertNotIn("Authorization", body)

    def test_mailerlite_endpoint_honest_when_not_connected(self):
        # Force the client to look for a MailerLite env that does not exist,
        # so the endpoint must report "not connected" rather than use the
        # a real newsletter key already present in the environment.
        no_key_env = (Path(self.temp.name) / "no-such-env").as_posix()
        with mock.patch.dict(os.environ, {"CONTENT_HUB_MAILERLITE_ENV": no_key_env}):
            self.server = self.build_server()
            status, body = self.request("/api/reporting/mailerlite?brand=brand-a")
            self.assertEqual(503, status)
            self.assertIn("not connected", body.get("error", "").lower())

    def test_mailerlite_endpoint_only_for_brand_a(self):
        self.server = self.build_server()
        status, body = self.request("/api/reporting/mailerlite?brand=brand-c")
        self.assertEqual(404, status)


if __name__ == "__main__":
    unittest.main()