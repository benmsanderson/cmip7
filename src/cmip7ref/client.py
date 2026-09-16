"""Thin HTTP client for the Climate REF API (https://api.climate-ref.org/docs).

The API is read-only and unauthenticated. Things to know about it:

* The API rejects Python's default user-agent with a 403, so we always send our own.
* Paginated endpoints return ``{"data": [...], "count": n, "total_count": N}``.
  Page size caps differ by endpoint (100 for datasets, 500 for metric values).
* The ``/values`` endpoints accept any dimension (``source_id``,
  ``experiment_id``, ...) as an extra query parameter to filter on.
* ``/datasets`` takes its facet filters as a JSON object in ``facets``.
* The ``/values`` endpoints return values from *every* execution of a group,
  including stale ones. :func:`cmip7ref.timeseries.latest_only` drops those.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.climate-ref.org/api/v1"
DEFAULT_CACHE_DIR = Path(".cache/ref-api")

# Largest page size each paginated endpoint accepts.
MAX_PAGE_SIZE = {"datasets": 100, "values": 500}


class RefClient:
    """Minimal client for the REF API, with an optional on-disk JSON cache.

    Parameters
    ----------
    base_url
        API root, including the ``/api/v1`` prefix.
    cache_dir
        Directory for cached responses. ``None`` disables caching.
    cache_ttl
        Seconds before a cached response is refetched.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
        cache_ttl: float = 6 * 3600,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.cache_ttl = cache_ttl
        self._http = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "cmip7ref/0.1", "Accept": "application/json"},
            follow_redirects=True,
        )

    # -- low level -------------------------------------------------------

    def get(self, path: str, **params: Any) -> Any:
        """GET ``path`` (relative to ``base_url``) and return the decoded JSON."""
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base_url}/{path.lstrip('/')}"
        cache_file = self._cache_file(url, params)
        if cache_file and cache_file.exists() and time.time() - cache_file.stat().st_mtime < self.cache_ttl:
            return json.loads(cache_file.read_text())

        resp = self._http.get(url, params=params)
        if resp.status_code >= 400:
            raise RefAPIError(resp.status_code, url, resp.text[:500])
        data = resp.json()

        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
        return data

    def paginate(self, path: str, page_size: int = 100, **params: Any) -> Iterator[dict]:
        """Yield every item from a paginated endpoint."""
        offset = 0
        while True:
            page = self.get(path, offset=offset, limit=page_size, **params)
            items = page["data"]
            yield from items
            offset += len(items)
            if not items or offset >= page["total_count"]:
                return

    def _cache_file(self, url: str, params: dict) -> Path | None:
        if self.cache_dir is None:
            return None
        key = json.dumps([url, sorted(params.items())], default=str)
        return self.cache_dir / f"{hashlib.sha1(key.encode()).hexdigest()}.json"

    # -- endpoints -------------------------------------------------------

    def about(self) -> dict:
        return self.get("utils/about")

    def models(self, mip_era: str = "CMIP7") -> list[dict]:
        return self.get("models/", mip_era=mip_era)["data"]

    def diagnostic_catalog(self, mip_era: str = "CMIP7") -> list[dict]:
        return self.get("diagnostics/catalog", mip_era=mip_era)["data"]

    def execution_groups(self, provider: str, diagnostic: str, mip_era: str = "CMIP7") -> list[dict]:
        return self.get(f"diagnostics/{provider}/{diagnostic}/execution_groups", mip_era=mip_era)["data"]

    def datasets(self, dataset_type: str = "cmip7", **facets: str) -> list[dict]:
        """List ingested datasets, filtered by facets (e.g. ``variable_id="tas"``)."""
        return list(
            self.paginate(
                "datasets/",
                page_size=MAX_PAGE_SIZE["datasets"],
                dataset_type=dataset_type,
                facets=json.dumps(facets) if facets else None,
            )
        )

    def metric_values(
        self,
        provider: str,
        diagnostic: str,
        value_type: str = "series",
        mip_era: str = "CMIP7",
        **dimensions: str,
    ) -> list[dict]:
        """All scalar or series values for a diagnostic, filtered by dimensions."""
        return list(
            self.paginate(
                f"diagnostics/{provider}/{diagnostic}/values",
                page_size=MAX_PAGE_SIZE["values"],
                value_type=value_type,
                mip_era=mip_era,
                **dimensions,
            )
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> RefClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class RefAPIError(RuntimeError):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} from {url}: {body}")
        self.status = status
