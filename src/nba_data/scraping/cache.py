from __future__ import annotations

import gzip
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse


class HtmlCache:
    """Filesystem cache for raw HTML stored as `.html.gz` files."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def get(self, url: str) -> str | None:
        path = self.path_for_url(url)
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return file.read()

    def set(self, url: str, html: str) -> Path:
        path = self.path_for_url(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as file:
            file.write(html)
        return path

    def exists(self, url: str) -> bool:
        return self.path_for_url(url).exists()

    def path_for_url(self, url: str) -> Path:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        if host == "basketball-reference.com":
            host_dir = "basketball-reference"
        else:
            host_dir = _safe_part(host or "unknown-host")

        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        slug_source = f"{parsed.path}-{parsed.query}".strip("-") or "index"
        slug = _safe_part(slug_source).strip("-")[:80] or "index"
        candidate = self.root_dir / host_dir / f"{slug}-{digest[:16]}.html.gz"

        root = self.root_dir.resolve(strict=False)
        resolved = candidate.resolve(strict=False)
        if root not in resolved.parents and resolved != root:
            msg = f"Cache path escaped root: {resolved}"
            raise ValueError(msg)
        return candidate


def _safe_part(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
