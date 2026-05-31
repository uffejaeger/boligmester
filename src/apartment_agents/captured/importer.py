from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(slots=True)
class CapturedListingImportResult:
    url: str
    document_name: str
    document_path: Path
    replaced_existing: bool


class CapturedListingImporter:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("examples")
        self.capture_dir = self.root / "captured_listings"
        self.index_path = self.capture_dir / "index.json"

    def import_html(
        self,
        *,
        url: str,
        source_html_path: Path,
        document_name: str | None = None,
    ) -> CapturedListingImportResult:
        html = source_html_path.read_text(encoding="utf-8")
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        index = self._load_index()
        existing_document_name = self._existing_document_name(index, url)
        resolved_document_name = document_name or existing_document_name or self._default_document_name(url)
        document_path = self.capture_dir / resolved_document_name
        document_path.write_text(html, encoding="utf-8")
        replaced_existing = existing_document_name is not None
        updated = False
        for item in index["items"]:
            if item["url"] == url:
                item["document"] = resolved_document_name
                updated = True
                break
        if not updated:
            index["items"].append(
                {
                    "url": url,
                    "document": resolved_document_name,
                }
            )
        index["items"] = sorted(index["items"], key=lambda item: str(item["url"]))
        self.index_path.write_text(json.dumps(index, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return CapturedListingImportResult(
            url=url,
            document_name=resolved_document_name,
            document_path=document_path,
            replaced_existing=replaced_existing,
        )

    def _load_index(self) -> dict[str, list[dict[str, str]]]:
        if not self.index_path.exists():
            return {"items": []}
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError("Captured listing index must contain an items list.")
        return {"items": items}

    def _existing_document_name(self, index: dict[str, list[dict[str, str]]], url: str) -> str | None:
        for item in index["items"]:
            if item["url"] == url:
                return str(item["document"])
        return None

    def _default_document_name(self, url: str) -> str:
        parsed = urlparse(url)
        candidate = parsed.path.rstrip("/").split("/")[-1] or "listing"
        slug = re.sub(r"[^a-z0-9]+", "_", candidate.lower()).strip("_")
        return f"{slug or 'listing'}_capture.html"
