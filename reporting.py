"""Read-only reporting sources for the Content Hub.

The source registry is the single inventory of what each brand has connected
(read-only, verified) versus what merely exists (account) versus what is not
wired at all. The GSC client refreshes the profile-local read-only token and
queries Search Analytics without ever exposing token values.

No paid APIs are called here. Brand B has no verified source and is marked
not connected instead of showing invented figures.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import json
import os

import requests

GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
WEBMASTERS_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class GscError(Exception):
    """Raised when GSC is not configured or a read failed."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _profile_home() -> Path:
    configured = os.environ.get("HERMES_HOME", "").strip()
    if configured:
        return Path(configured)
    return Path.home() / ".hermes"


def default_gsc_token_path() -> Path:
    override = os.environ.get("CONTENT_HUB_GSC_TOKEN_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return _profile_home() / "google_gsc_token.json"


def default_mailerlite_env_path() -> Path | None:
    override = os.environ.get("CONTENT_HUB_MAILERLITE_ENV", "").strip()
    if override:
        return Path(override).expanduser() if Path(override).exists() else None
    candidate = Path(".env.local")
    return candidate if candidate.exists() else None


SOURCE_REGISTRY: dict[str, list[dict[str, str]]] = {
    "brand-a": [
        {
            "kind": "gsc",
            "status": "verified",
            "label": "Google Search Console",
            "property": "https://www.brand-a.example.com/",
            "permission": "siteOwner",
            "description": "Example: a Search Console property connected read-only for this brand.",
        },
        {
            "kind": "newsletter",
            "status": "verified",
            "label": "Newsletter analytics",
            "description": "Example: a read-only newsletter provider connected for this brand's list.",
        },
        {
            "kind": "pagespeed",
            "status": "verified",
            "label": "PageSpeed Insights",
            "url": "https://www.brand-a.example.com/",
            "description": "Free PageSpeed Insights scores (performance, accessibility, best practices, SEO).",
        },
        {
            "kind": "site",
            "status": "account_available",
            "label": "Website",
            "description": "Example site. No analytics connection is wired.",
        },
        {
            "kind": "social",
            "status": "account_available",
            "label": "X",
            "description": "Example social account. No read-only analytics connection is wired.",
        },
    ],
    "brand-b": [
        {
            "kind": "gsc",
            "status": "not_connected",
            "label": "Google Search Console",
            "description": "Not connected.",
        },
        {
            "kind": "site",
            "status": "not_connected",
            "label": "Website / app",
            "description": "Not connected.",
        },
        {
            "kind": "social",
            "status": "not_connected",
            "label": "Social accounts",
            "description": "Not connected.",
        },
        {
            "kind": "store",
            "status": "account_available",
            "label": "App store listing",
            "description": "Example store listing. No read-only store analytics connection is wired.",
        },
    ],
    "brand-c": [
        {
            "kind": "gsc",
            "status": "verified",
            "label": "Google Search Console",
            "property": "https://www.brand-c.example.com/",
            "permission": "siteOwner",
            "description": "Example: a Search Console property connected read-only for this brand.",
        },
        {
            "kind": "site",
            "status": "account_available",
            "label": "Website",
            "description": "Example site. No analytics connection is wired.",
        },
        {
            "kind": "pagespeed",
            "status": "verified",
            "label": "PageSpeed Insights",
            "url": "https://www.brand-c.example.com/",
            "description": "Free PageSpeed Insights scores (performance, accessibility, best practices, SEO).",
        },
        {
            "kind": "newsletter",
            "status": "not_connected",
            "label": "Newsletter / email analytics",
            "description": "Not connected.",
        },
        {
            "kind": "social",
            "status": "not_connected",
            "label": "YouTube",
            "description": "Not connected.",
        },
    ],
}


def source_for_brand(brand_id: str, kind: str = "gsc") -> dict[str, str] | None:
    for source in SOURCE_REGISTRY.get(brand_id, []):
        if source["kind"] == kind:
            return source
    return None


class GscClient:
    """Minimal read-only Google Search Console client.

    Uses the profile-local token created by scripts/google_gsc_oauth.py with
    only the webmasters.readonly scope. Token values are never logged or
    returned by this class.
    """

    def __init__(self, token_path: str | Path | None = None):
        self.token_path = Path(token_path) if token_path else default_gsc_token_path()

    def _token(self) -> dict:
        if not self.token_path.exists():
            raise GscError("Google Search Console is not authenticated.", 503)
        try:
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GscError(f"Could not read GSC token: {exc}", 503) from exc
        if WEBMASTERS_SCOPE not in set(data.get("scopes", [])):
            raise GscError("GSC token is missing the read-only scope.", 503)
        return data

    def _refresh(self, data: dict) -> None:
        if not data.get("refresh_token"):
            raise GscError("GSC token has no refresh credential; re-run the OAuth helper.", 503)
        response = requests.post(
            data.get("token_uri", "https://oauth2.googleapis.com/token"),
            data={
                "grant_type": "refresh_token",
                "client_id": data["client_id"],
                "client_secret": data["client_secret"],
                "refresh_token": data["refresh_token"],
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise GscError("GSC token refresh failed; re-authorize.", 503)
        updated = response.json()
        data["token"] = updated["access_token"]
        if "expires_in" in updated:
            import datetime as dt

            data["expiry"] = (
                dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=updated["expires_in"])
            ).isoformat()
        self.token_path.write_text(json.dumps(data, indent=2))

    def _access_token(self) -> str:
        data = self._token()
        import datetime as dt

        expiry = data.get("expiry")
        if expiry:
            try:
                parsed = dt.datetime.fromisoformat(expiry)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                if parsed <= dt.datetime.now(dt.timezone.utc):
                    self._refresh(data)
            except ValueError:
                self._refresh(data)
        return data["token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token()}"}

    def list_sites(self) -> list[dict[str, str]]:
        response = requests.get(
            f"{GSC_API_BASE}/sites/", headers=self._headers(), timeout=30
        )
        if response.status_code != 200:
            raise GscError("Google Search Console is not reachable right now.", 502)
        entries = response.json().get("siteEntry", [])
        return [
            {
                "siteUrl": entry.get("siteUrl", ""),
                "permissionLevel": entry.get("permissionLevel", ""),
            }
            for entry in entries
        ]

    def search_analytics(
        self, site_url: str, start_date: date, end_date: date
    ) -> list[dict]:
        payload = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": [],
            "rowLimit": 1,
            "type": "web",
        }
        encoded = quote(site_url, safe="")
        response = requests.post(
            f"{GSC_API_BASE}/sites/{encoded}/searchAnalytics/query",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        if response.status_code != 200:
            raise GscError("Google Search Console could not answer the read query.", 502)
        return response.json().get("rows", [])


def build_reports_payload() -> dict:
    return {"sources": SOURCE_REGISTRY}


class PageSpeedClient:
    """Free PageSpeed Insights (v5) reader; no API key required."""

    PAGE_SPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def run(self, url: str, strategy: str = "mobile") -> dict:
        try:
            response = requests.get(
                self.PAGE_SPEED_API,
                params={"url": url, "strategy": strategy, "category": "performance"},
                timeout=60,
            )
        except requests.RequestException as exc:
            raise GscError(f"PageSpeed call failed: {exc}", 502) from exc
        if response.status_code == 429 or response.status_code == 403:
            raise GscError("PageSpeed Insights quota is exhausted right now.", 429)
        if response.status_code != 200:
            raise GscError("PageSpeed Insights could not answer right now.", 502)
        data = response.json()
        categories = data.get("lighthouseResult", {}).get("categories", {})
        scores = {}
        for name in ("performance", "accessibility", "best-practices", "seo"):
            cat = categories.get(name, {})
            raw = cat.get("score")
            scores[name] = int(round(raw * 100)) if raw is not None else None
        return {"scores": scores, "fetchTime": data.get("lighthouseResult", {}).get("fetchTime")}


class MailerLiteClient:
    """Read-only MailerLite reader using the Brand A account's API key.

    The key is read from the AccDevSite project's .env.local which is the
    documented home of the Brand A MailerLite key. It is never logged or returned.
    """

    BASE = "https://connect.mailerlite.com/api"
    ACC_ONLY_ENV_PATH = ".env.local"

    def __init__(self, env_path: str | Path | None = None):
        self._env_path = Path(env_path) if env_path else default_mailerlite_env_path()
        self._api_key = None  # loaded lazily so server startup never fails

    def _key(self) -> str:
        if self._api_key is None:
            self._api_key = self._load_key(self._env_path)
        return self._api_key

    @staticmethod
    def _load_key(env_path: Path | None) -> str:
        if env_path is None or not env_path.exists():
            raise GscError("MailerLite is not connected (no Brand A account key available).", 503)
        try:
            value = None
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("MAILERLITE_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip("'\"").strip()
                    break
            if not value:
                raise GscError("MailerLite is not connected (no key found).", 503)
            return value
        except OSError as exc:
            raise GscError(f"MailerLite key could not be read: {exc}", 503) from exc

    def _get(self, path: str) -> dict:
        try:
            response = requests.get(
                f"{self.BASE}{path}",
                headers={"Authorization": f"Bearer {self._key()}"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise GscError(f"MailerLite call failed: {exc}", 502) from exc
        if response.status_code == 401:
            raise GscError("MailerLite key rejected; re-check the Brand A account key.", 503)
        if response.status_code != 200:
            raise GscError("MailerLite could not answer right now.", 502)
        return response.json()

    def list_groups(self) -> list[dict]:
        data = self._get("/groups?limit=100")
        return data.get("data", [])


class ReportingStore:
    """Server-side facade over the read-only reporting sources."""

    def __init__(
        self,
        gsc_client: GscClient | None = None,
        pagespeed_client: PageSpeedClient | None = None,
        mailerlite_client: MailerLiteClient | None = None,
    ):
        self._gsc = gsc_client if gsc_client is not None else GscClient()
        self._pagespeed = (
            pagespeed_client if pagespeed_client is not None else PageSpeedClient()
        )
        self._mailerlite = (
            mailerlite_client if mailerlite_client is not None else MailerLiteClient()
        )

    def sources_payload(self) -> dict:
        return {"sources": SOURCE_REGISTRY}

    def gsc_baseline(self, brand_id: str, days: int = 28) -> dict:
        try:
            return fetch_gsc_baseline(self._gsc, brand_id, days=days)
        except GscError:
            raise
        except Exception as exc:  # provider or transport failures stay honest
            raise GscError(f"Source unavailable: {exc}", 502) from exc

    def pagespeed(self, brand_id: str, strategy: str = "mobile") -> dict:
        try:
            source = source_for_brand(brand_id, "pagespeed")
            if not source or source["status"] != "verified":
                raise GscError(f"{brand_id} has no verified PageSpeed source.", 404)
            url = source["url"]
            result = self._pagespeed.run(url, strategy=strategy)
            return {"brand": brand_id, "url": url, "strategy": strategy, **result}
        except GscError:
            raise
        except Exception as exc:
            raise GscError(f"Source unavailable: {exc}", 502) from exc

    def mailerlite(self, brand_id: str) -> dict:
        if brand_id != "brand-a":
            raise GscError("MailerLite reporting is wired only for brand-a.", 404)
        try:
            groups = [self._group_summary(g) for g in self._mailerlite.list_groups()]
            return {"brand": brand_id, "groups": groups}
        except GscError:
            raise
        except Exception as exc:
            raise GscError(f"Source unavailable: {exc}", 502) from exc

    @staticmethod
    def _group_summary(group: dict) -> dict:
        open_rate = group.get("open_rate")
        click_rate = group.get("click_rate")
        return {
            "id": group.get("id"),
            "name": group.get("name"),
            "active_count": group.get("active_count"),
            "sent_count": group.get("sent_count"),
            "opens_count": group.get("opens_count"),
            "click_count": group.get("clicks_count"),
            "open_rate": open_rate.get("float") if isinstance(open_rate, dict) else open_rate,
            "click_rate": click_rate.get("float") if isinstance(click_rate, dict) else click_rate,
            "unsubscribed_count": group.get("unsubscribed_count"),
        }


def fetch_gsc_baseline(
    gsc: GscClient, brand_id: str, days: int = 28
) -> dict:
    """Read-only 28-day aggregate for the brand's verified GSC property."""
    source = source_for_brand(brand_id, "gsc")
    if not source or source["status"] != "verified":
        raise GscError(f"{brand_id} is not connected to Google Search Console.", 404)
    property_url = source["property"]
    sites = gsc.list_sites()
    matched = next((entry for entry in sites if entry.get("siteUrl") == property_url), None)
    if matched is None:
        # Property is no longer visible under this token.
        raise GscError("The verified property is no longer visible to this token.", 502)

    end = date.today()
    start = end - timedelta(days=max(0, days - 1))
    rows = gsc.search_analytics(property_url, start, end)
    row = rows[0] if rows else {}
    return {
        "property": property_url,
        "permission": matched.get("permissionLevel", ""),
        "window": {"startDate": start.isoformat(), "endDate": end.isoformat()},
        "metrics": {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr"),
            "averagePosition": row.get("averagePosition"),
        },
    }