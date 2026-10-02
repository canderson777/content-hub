"""Local-only Content Hub server and Marketing Agent OS asset bridge."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from content_store import ContentError, ContentStore
from reporting import GscError, ReportingStore


BRANDS = {
    "brand-a": {"label": "Brand A", "folder": "brand-a"},
    "brand-b": {"label": "Brand B", "folder": "brand-b"},
    "brand-c": {"label": "Brand C", "folder": "brand-c"},
}

UPLOAD_CATEGORIES = {
    "logos": "logos",
    "brand-guidelines": "brand-guidelines",
    "product-shots": "product-shots",
    "studio-shots": "studio-shots",
    "social-post-images": "social/post-images",
    "social-thumbnails": "social/thumbnails",
    "social-covers-banners": "social/covers-banners",
    "finished-outputs": "outputs/social",
}

SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".mp4",
    ".webm",
    ".mov",
    ".pdf",
}
MAX_UPLOAD_BYTES = 40 * 1024 * 1024


class AssetError(Exception):
    """Expected asset-library error with an HTTP status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class AssetLibrary:
    """Read/write only allowlisted brand asset folders under one brands root."""

    def __init__(self, brands_root: str | Path, max_upload_bytes: int = MAX_UPLOAD_BYTES):
        self.brands_root = Path(brands_root).expanduser().resolve()
        self.max_upload_bytes = max_upload_bytes

    def list_brands(self) -> list[dict[str, Any]]:
        result = []
        for brand_id, brand in BRANDS.items():
            asset_root = self._asset_root(brand_id)
            result.append(
                {
                    "id": brand_id,
                    "label": brand["label"],
                    "folder_exists": asset_root.is_dir(),
                    "asset_count": len(self.list_assets(brand_id)),
                }
            )
        return result

    def list_assets(self, brand_id: str) -> list[dict[str, Any]]:
        asset_root = self._asset_root(brand_id)
        if not asset_root.is_dir():
            return []
        root_resolved = asset_root.resolve()
        results = []
        for current, directory_names, file_names in os.walk(asset_root, followlinks=False):
            current_path = Path(current)
            directory_names[:] = [
                name
                for name in directory_names
                if not name.startswith(".") and not (current_path / name).is_symlink()
            ]
            for name in file_names:
                candidate = current_path / name
                if candidate.is_symlink() or candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root_resolved)
                    stat = resolved.stat()
                except (OSError, ValueError):
                    continue
                results.append(self._record(brand_id, asset_root, resolved, stat))
        results.sort(key=lambda item: (item["path"].casefold(), item["name"].casefold()))
        return results

    def resolve_asset(self, brand_id: str, relative_path: str) -> Path:
        asset_root = self._asset_root(brand_id)
        if not asset_root.is_dir():
            raise AssetError("Brand asset folder does not exist.", 404)
        if not relative_path or "\\" in relative_path or "\x00" in relative_path:
            raise AssetError("Invalid asset path.", 400)
        parts = PurePosixPath(relative_path).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise AssetError("Invalid asset path.", 400)
        candidate = asset_root.joinpath(*parts)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(asset_root.resolve())
        except (OSError, ValueError):
            raise AssetError("Asset not found.", 404) from None
        if not resolved.is_file() or resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise AssetError("Asset not found.", 404)
        return resolved

    def save_upload(self, brand_id: str, category: str, filename: str, data: bytes) -> dict[str, Any]:
        self._brand(brand_id)
        category_path = UPLOAD_CATEGORIES.get(category)
        if category_path is None:
            raise AssetError("Choose a supported destination folder.", 400)
        if (
            not filename
            or filename in {".", ".."}
            or filename.startswith(".")
            or "/" in filename
            or "\\" in filename
            or "\x00" in filename
            or len(filename) > 180
        ):
            raise AssetError("Use a plain filename without a folder path.", 400)
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise AssetError("This file type is not supported.", 415)
        if not data:
            raise AssetError("The selected file is empty.", 400)
        if len(data) > self.max_upload_bytes:
            raise AssetError("File exceeds the 40 MB upload limit.", 413)

        asset_root = self._asset_root(brand_id)
        asset_root.mkdir(parents=True, exist_ok=True)
        destination_dir = asset_root / category_path
        destination_dir.mkdir(parents=True, exist_ok=True)
        try:
            destination_dir.resolve().relative_to(asset_root.resolve())
        except ValueError:
            raise AssetError("Destination folder is outside the brand asset library.", 400) from None
        destination = destination_dir / filename
        try:
            with destination.open("xb") as output:
                output.write(data)
            resolved = destination.resolve(strict=True)
            resolved.relative_to(asset_root.resolve())
            return self._record(brand_id, asset_root, resolved, resolved.stat())
        except FileExistsError:
            raise AssetError("A file with that name already exists. Rename it first; existing files are never overwritten.", 409) from None
        except ValueError:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
            raise AssetError("Destination file is outside the brand asset library.", 400) from None

    def _brand(self, brand_id: str) -> dict[str, str]:
        brand = BRANDS.get(brand_id)
        if brand is None:
            raise AssetError("Unknown brand.", 404)
        return brand

    def _asset_root(self, brand_id: str) -> Path:
        brand = self._brand(brand_id)
        root = self.brands_root.resolve()
        brand_root = self.brands_root / brand["folder"]
        try:
            brand_root.resolve().relative_to(root)
            asset_root = brand_root / "assets"
            asset_root.resolve().relative_to(brand_root.resolve())
        except ValueError:
            raise AssetError("Configured brand folder resolves outside the brands directory.", 400) from None
        return asset_root

    @staticmethod
    def _record(brand_id: str, asset_root: Path, path: Path, stat: os.stat_result) -> dict[str, Any]:
        relative = path.relative_to(asset_root.resolve()).as_posix()
        extension = path.suffix.lower()
        if extension == ".pdf":
            kind = "document"
        elif extension in {".mp4", ".webm", ".mov"}:
            kind = "video"
        else:
            kind = "image"
        review_required = (
            any(part.casefold() in {"source-review", "review-only", "_unused"} for part in PurePosixPath(relative).parts)
            or "review-only" in path.name.casefold()
        )
        return {
            "brand": brand_id,
            "name": path.name,
            "path": relative,
            "category": str(PurePosixPath(relative).parent),
            "kind": kind,
            "review_required": review_required,
            "extension": extension.lstrip("."),
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "url": f"/brand-assets/{quote(brand_id)}/{quote(relative, safe='/')}",
        }


class BrandProfileLibrary:
    """Read allowlisted profile documents and keep edits in the Hub database."""

    REQUIRED_FILES = (
        "brand-voice.md",
        "audience.md",
        "offers.md",
        "content-pillars.md",
        "positions/three-ps.md",
    )
    SOURCE_FILES = (*REQUIRED_FILES[:3], "links-and-assets.md", *REQUIRED_FILES[3:])

    def __init__(self, brands_root: str | Path, content_store: ContentStore):
        self.brands_root = Path(brands_root).expanduser().resolve()
        self.content_store = content_store

    def get_profile(self, brand_id: str) -> dict[str, Any]:
        brand = BRANDS.get(brand_id)
        if brand is None:
            raise ContentError("Unknown brand profile.", 404)
        source = self._read_source_profile(brand)
        override = self.content_store.get_brand_profile_override(brand_id)
        return {
            "brandId": brand_id,
            "label": brand["label"],
            "fields": override["fields"] if override else source["fields"],
            "sourceFiles": source["sourceFiles"],
            "missingFiles": source["missingFiles"],
            "sourceStatus": "incomplete" if source["missingFiles"] else "complete",
            "sourceUpdatedAt": source["sourceUpdatedAt"],
            "isCustomized": override is not None,
            "updatedAt": override["savedAt"] if override else None,
        }

    def _read_source_profile(self, brand: dict[str, str]) -> dict[str, Any]:
        documents: dict[str, str] = {}
        source_files: list[str] = []
        modified_times: list[float] = []
        for relative_path in self.SOURCE_FILES:
            result = self._read_document(brand["folder"], relative_path)
            if result is None:
                continue
            text, modified = result
            documents[relative_path] = text
            source_files.append(relative_path)
            modified_times.append(modified)

        voice_document = documents.get("brand-voice.md", "")
        voice_parts = [
            self._extract_section(voice_document, heading)
            for heading in (
                "Voice summary",
                "Tone traits",
                "Words / phrases to use",
                "Example style notes",
                "Example on-voice copy",
                "Reference notes",
            )
        ]
        voice_style = "\n\n".join(part for part in voice_parts if part).strip()
        if not voice_style:
            voice_style = self._without_title(voice_document)

        offer_parts = [self._without_title(documents.get("offers.md", ""))]
        links_document = documents.get("links-and-assets.md", "")
        if links_document:
            offer_parts.append("## Links and assets\n" + self._without_title(links_document))

        fields = {
            "voiceStyle": voice_style,
            "audience": self._without_title(documents.get("audience.md", "")),
            "offerAndLinks": "\n\n".join(part for part in offer_parts if part).strip(),
            "ctaStyle": self._extract_section(voice_document, "CTA style"),
            "neverUse": self._extract_section(voice_document, "Words / phrases to avoid"),
            "contentPillars": self._without_title(documents.get("content-pillars.md", "")),
            "positioning": self._without_title(documents.get("positions/three-ps.md", "")),
        }
        missing_files = [path for path in self.REQUIRED_FILES if path not in documents]
        updated_at = None
        if modified_times:
            updated_at = datetime.fromtimestamp(max(modified_times), timezone.utc).isoformat(timespec="seconds")
        return {
            "fields": fields,
            "sourceFiles": source_files,
            "missingFiles": missing_files,
            "sourceUpdatedAt": updated_at,
        }

    def _read_document(self, brand_folder: str, relative_path: str) -> tuple[str, float] | None:
        try:
            brand_root = (self.brands_root / brand_folder).resolve(strict=True)
            brand_root.relative_to(self.brands_root)
            candidate = brand_root
            for part in PurePosixPath(relative_path).parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    return None
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(brand_root)
            if not resolved.is_file() or resolved.suffix.lower() != ".md":
                return None
            stat = resolved.stat()
            return resolved.read_text(encoding="utf-8-sig"), stat.st_mtime
        except (OSError, UnicodeError, ValueError):
            return None

    @staticmethod
    def _without_title(markdown: str) -> str:
        lines = markdown.splitlines()
        if lines and re.match(r"^#\s+", lines[0]):
            lines = lines[1:]
        return "\n".join(lines).strip()

    @staticmethod
    def _normalize_heading(title: str) -> str:
        return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip().casefold()

    @classmethod
    def _extract_section(cls, markdown: str, title: str) -> str:
        lines = markdown.splitlines()
        selected: list[str] = []
        found = False
        for line in lines:
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading:
                level = len(heading.group(1))
                if found and level <= 2:
                    break
                if level == 2 and cls._normalize_heading(heading.group(2)) == cls._normalize_heading(title):
                    found = True
                    selected.append(line)
                    continue
            if found:
                selected.append(line)
        return "\n".join(selected).strip()


class LocalHubServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            content_store = getattr(self, "content_store", None)
            if content_store is not None:
                content_store.close()


def create_server(
    project_dir: str | Path,
    brands_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    content_db_path: str | Path | None = None,
    gsc_client: Any | None = None,
    pagespeed_client: Any | None = None,
    mailerlite_client: Any | None = None,
) -> LocalHubServer:
    project_path = Path(project_dir).resolve()
    store = AssetLibrary(brands_root)
    content_store = ContentStore(content_db_path if content_db_path is not None else ":memory:")
    profile_library = BrandProfileLibrary(brands_root, content_store)
    reporting_store = ReportingStore(gsc_client, pagespeed_client, mailerlite_client)

    class HubRequestHandler(SimpleHTTPRequestHandler):
        server_version = "ContentHubLocal/1.0"

        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=str(project_path), **kwargs)

        def parse_request(self) -> bool:
            if not super().parse_request():
                return False
            host_header = self.headers.get("Host", "")
            try:
                request_host = urlsplit(f"//{host_header}")
            except ValueError:
                self.send_error(403, "Local requests only")
                return False
            if request_host.hostname not in {"localhost", "127.0.0.1"}:
                self.send_error(403, "Local requests only")
                return False
            fetch_site = self.headers.get("Sec-Fetch-Site", "").lower()
            if fetch_site in {"cross-site"} or not self._same_origin():
                self.send_error(403, "Cross-origin requests are blocked")
                return False
            return True

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path == "/api/health":
                self._json(200, {"status": "ok", "service": "content-hub-local"})
                return
            if parsed.path == "/api/brands":
                self._json(200, {"brands": store.list_brands()})
                return
            if parsed.path == "/api/assets":
                try:
                    brand_id = self._one_query_value(parsed.query, "brand")
                    self._json(200, {"brand": brand_id, "assets": store.list_assets(brand_id)})
                except AssetError as error:
                    self._json(error.status, {"error": str(error)})
                return
            if parsed.path == "/api/content":
                try:
                    brand_id = self._one_query_value(parsed.query, "brand")
                    self._json(200, {"brand": brand_id, "records": content_store.list_records(brand_id)})
                except (AssetError, ContentError) as error:
                    self._json(error.status, {"error": str(error)})
                return
            if parsed.path == "/api/reporting/sources":
                self._json(200, reporting_store.sources_payload())
                return
            if parsed.path == "/api/reporting/gsc":
                try:
                    brand_id = self._one_query_value(parsed.query, "brand")
                    self._json(200, reporting_store.gsc_baseline(brand_id))
                except GscError as error:
                    self._json(error.status, {"error": str(error)})
                except ContentError as error:
                    self._json(error.status, {"error": str(error)})
                return
            if parsed.path == "/api/reporting/pagespeed":
                try:
                    brand_id = self._one_query_value(parsed.query, "brand")
                    self._json(200, reporting_store.pagespeed(brand_id))
                except GscError as error:
                    self._json(error.status, {"error": str(error)})
                except ContentError as error:
                    self._json(error.status, {"error": str(error)})
                return
            if parsed.path == "/api/reporting/mailerlite":
                try:
                    brand_id = self._one_query_value(parsed.query, "brand")
                    self._json(200, reporting_store.mailerlite(brand_id))
                except GscError as error:
                    self._json(error.status, {"error": str(error)})
                except ContentError as error:
                    self._json(error.status, {"error": str(error)})
                return
            if parsed.path == "/api/brand-profile":
                try:
                    brand_id = self._one_query_value(parsed.query, "brand")
                    self._json(200, {"profile": profile_library.get_profile(brand_id)})
                except (AssetError, ContentError) as error:
                    self._json(error.status, {"error": str(error)})
                return
            if parsed.path.startswith("/brand-assets/"):
                self._serve_brand_asset(parsed.path)
                return
            super().do_GET()

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path == "/api/content/drafts":
                self._create_content_record(draft=True)
                return
            if parsed.path == "/api/content":
                self._create_content_record()
                return
            if parsed.path.startswith("/api/content/"):
                self._apply_content_action(parsed.path)
                return
            if parsed.path != "/api/upload":
                self._json(404, {"error": "Endpoint not found."})
                return
            if not self._same_origin():
                self._json(403, {"error": "Cross-origin uploads are blocked."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "Invalid Content-Length."})
                return
            if length <= 0:
                self._json(400, {"error": "The upload body is empty."})
                return
            if length > store.max_upload_bytes:
                self._json(413, {"error": "File exceeds the 40 MB upload limit."})
                return
            query = parse_qs(parsed.query, keep_blank_values=True)
            try:
                brand_id = self._query_value(query, "brand")
                category = self._query_value(query, "category")
                filename = self._query_value(query, "name")
                data = self.rfile.read(length)
                if len(data) != length:
                    raise AssetError("Upload ended before all file data arrived.", 400)
                asset = store.save_upload(brand_id, category, filename, data)
            except AssetError as error:
                self._json(error.status, {"error": str(error)})
                return
            except (KeyError, ValueError):
                self._json(400, {"error": "Upload requires one brand, category, and filename."})
                return
            self._json(201, {"asset": asset})

        def do_PUT(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path != "/api/brand-profile":
                self._json(404, {"error": "Endpoint not found."})
                return
            try:
                brand_id = self._one_query_value(parsed.query, "brand")
                payload = self._read_json_body()
                if set(payload) != {"fields"}:
                    raise ContentError("Send only the brand profile fields.")
                content_store.save_brand_profile_override(brand_id, payload["fields"])
                self._json(200, {"profile": profile_library.get_profile(brand_id)})
            except (AssetError, ContentError) as error:
                self._json(error.status, {"error": str(error)})

        def do_DELETE(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path != "/api/brand-profile":
                self._json(404, {"error": "Endpoint not found."})
                return
            try:
                brand_id = self._one_query_value(parsed.query, "brand")
                content_store.reset_brand_profile_override(brand_id)
                self._json(200, {"profile": profile_library.get_profile(brand_id)})
            except (AssetError, ContentError) as error:
                self._json(error.status, {"error": str(error)})

        def _read_json_body(self) -> Any:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ContentError("Invalid Content-Length.") from None
            if length <= 0:
                raise ContentError("The JSON request body is empty.")
            if length > 1_000_000:
                raise ContentError("The JSON request body exceeds the 1 MB limit.", 413)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ContentError("Request ended before all JSON data arrived.")
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ContentError("Request body must be valid UTF-8 JSON.") from None
            if not isinstance(payload, dict):
                raise ContentError("A JSON object is required.")
            return payload

        def _create_content_record(self, draft: bool = False) -> None:
            try:
                create_record = content_store.create_draft if draft else content_store.create_submission
                record = create_record(self._read_json_body())
            except ContentError as error:
                self._json(error.status, {"error": str(error)})
                return
            self._json(201, {"record": record})

        def _apply_content_action(self, path: str) -> None:
            prefix = "/api/content/"
            remainder = path[len(prefix):]
            record_id, separator, action_path = remainder.partition("/")
            if not separator or action_path != "actions" or not record_id:
                self._json(404, {"error": "Endpoint not found."})
                return
            try:
                record = content_store.apply_action(record_id, self._read_json_body())
            except ContentError as error:
                self._json(error.status, {"error": str(error)})
                return
            self._json(200, {"record": record})

        def _serve_brand_asset(self, path: str) -> None:
            prefix = "/brand-assets/"
            remainder = path[len(prefix) :]
            brand_part, separator, asset_part = remainder.partition("/")
            if not separator:
                self._json(404, {"error": "Asset not found."})
                return
            try:
                asset_path = store.resolve_asset(unquote(brand_part), unquote(asset_part))
                stat = asset_path.stat()
                content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(stat.st_size))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                if asset_path.suffix.lower() == ".svg":
                    self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; sandbox")
                self.end_headers()
                with asset_path.open("rb") as source:
                    while block := source.read(64 * 1024):
                        self.wfile.write(block)
            except AssetError as error:
                self._json(error.status, {"error": str(error)})
            except OSError:
                self._json(404, {"error": "Asset not found."})

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            try:
                source = urlsplit(origin)
                host = urlsplit(f"//{self.headers.get('Host', '')}")
                return (
                    source.scheme == "http"
                    and source.hostname in {"localhost", "127.0.0.1"}
                    and host.hostname in {"localhost", "127.0.0.1"}
                    and (source.port or 80) == (host.port or 80)
                )
            except ValueError:
                return False

        def _json(self, status: int, data: dict[str, Any]) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        @staticmethod
        def _query_value(query: dict[str, list[str]], key: str) -> str:
            values = query.get(key, [])
            if len(values) != 1 or not values[0]:
                raise ValueError(f"Missing or repeated {key}.")
            return values[0]

        def _one_query_value(self, query_string: str, key: str) -> str:
            try:
                return self._query_value(parse_qs(query_string, keep_blank_values=True), key)
            except ValueError:
                raise AssetError(f"Missing {key}.", 400) from None

    server = LocalHubServer((host, port), HubRequestHandler)
    server.content_store = content_store
    return server


def default_content_db_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        data_root = Path(local_app_data)
    else:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_root / "ContentHub" / "content-hub.sqlite3"


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Content Hub and local brand asset library.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CONTENT_HUB_PORT", "8000")))
    args = parser.parse_args()
    project_dir = Path(__file__).resolve().parent
    brands_root = Path(
        os.environ.get(
            "CONTENT_HUB_BRANDS_ROOT",
            os.environ.get("MARKETING_AGENT_OS_BRANDS_ROOT", str(project_dir / "brands")),
        )
    ).expanduser()
    database_path = Path(os.environ.get("CONTENT_HUB_DB_PATH", default_content_db_path())).expanduser()
    try:
        server = create_server(project_dir, brands_root, port=args.port, content_db_path=database_path)
    except OSError as error:
        print(f"Could not start Content Hub on 127.0.0.1:{args.port}: {error}", file=sys.stderr)
        print("Stop any older server already using the port, then try again.", file=sys.stderr)
        return 1
    print(f"Content Hub: http://127.0.0.1:{args.port}")
    print("Local-only server. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Content Hub.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
