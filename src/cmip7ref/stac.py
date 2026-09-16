"""Client for the ESGF STAC API, which is where CMIP7 model output lives.

Notes on this API (see docs/data_availability.md):

* CMIP7 output is **not** in the legacy Solr index. It is only here.
* Filters must be CQL2 (``filter-lang: cql2-json``). The simpler STAC ``query``
  extension rejects the ``in`` operator, so we always speak CQL2.
* Properties are namespaced: ``cmip7:source_id``, ``cmip7:variable_branded_name``...
* Every item is ``access: ["HTTPServer"]`` — there is no OPeNDAP, so files have
  to be downloaded.
* ``end_datetime`` is an *exclusive* bound: an item ending ``2022-01-01`` holds
  data through December 2021.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

STAC_URL = "https://api.stac.esgf.ceda.ac.uk"
DEFAULT_CACHE_DIR = Path(".cache/esgf")

# Short names -> the namespaced property the API indexes them under.
FACETS = {
    "source_id": "cmip7:source_id",
    "experiment_id": "cmip7:experiment_id",
    "variable_id": "cmip7:variable_id",
    "branded": "cmip7:variable_branded_name",
    "variant_label": "cmip7:variant_label",
    "frequency": "cmip7:frequency",
    "grid_label": "cmip7:grid_label",
    "institution_id": "cmip7:institution_id",
}


@dataclass(frozen=True)
class StacItem:
    """One published dataset: a DRS instance id plus its netCDF files."""

    id: str
    properties: dict
    assets: dict

    def _p(self, key: str) -> Any:
        return self.properties.get(FACETS.get(key, key))

    @property
    def source_id(self) -> str:
        return self._p("source_id")

    @property
    def experiment_id(self) -> str:
        return self._p("experiment_id")

    @property
    def variant_label(self) -> str:
        return self._p("variant_label")

    @property
    def variable_id(self) -> str:
        return self._p("variable_id")

    @property
    def branded(self) -> str:
        return self._p("branded")

    @property
    def grid_label(self) -> str:
        return self._p("grid_label")

    @property
    def version(self) -> str:
        return self.properties.get("version")

    @property
    def units(self) -> str | None:
        return self.properties.get("cmip7:variable_units")

    @property
    def years(self) -> tuple[int | None, int | None]:
        """Inclusive first and last year. ``end_datetime`` is exclusive, so a
        January 1st end date means the previous year was the last full one."""
        start, end = self.properties.get("start_datetime"), self.properties.get("end_datetime")
        y0 = int(start[:4]) if start else None
        if not end:
            return y0, None
        y1 = int(end[:4])
        return y0, y1 - 1 if end[5:10] == "01-01" else y1

    @property
    def size(self) -> int:
        return self.properties.get("size") or 0

    def files(self) -> list[tuple[str, str, int]]:
        """``(filename, url, expected_size)`` for each netCDF file, in name order."""
        out = []
        for name, a in self.assets.items():
            if a.get("type") == "application/netcdf" or name.endswith(".nc"):
                out.append((name, a["href"], a.get("file:size") or 0))
        return sorted(out)

    def __str__(self) -> str:
        y0, y1 = self.years
        return f"{self.branded} {self.experiment_id} {self.variant_label} v{self.version} ({y0}-{y1})"


class StacClient:
    """Search the CMIP7 STAC index and download the files it points at."""

    def __init__(
        self,
        url: str = STAC_URL,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        timeout: float = 180.0,
        collection: str = "CMIP7",
    ):
        self.url = url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.collection = collection
        self._http = httpx.Client(
            timeout=timeout, headers={"User-Agent": "cmip7ref/0.1"}, follow_redirects=True
        )

    # -- search ----------------------------------------------------------

    @staticmethod
    def _cql2(filters: dict[str, Any]) -> dict:
        """Build a CQL2 ``and`` of ``=``/``in`` tests from short facet names."""
        args = []
        for key, value in filters.items():
            if value is None:
                continue
            prop = {"property": FACETS.get(key, key)}
            if isinstance(value, (list, tuple, set)):
                args.append({"op": "in", "args": [prop, sorted(value)]})
            else:
                args.append({"op": "=", "args": [prop, value]})
        if not args:
            raise ValueError("at least one filter is required")
        return args[0] if len(args) == 1 else {"op": "and", "args": args}

    def search(self, page_size: int = 500, cap: int = 20000, **filters: Any) -> list[StacItem]:
        """Search items. Filters take a value or a list, e.g. ``variant_label=["r1i1p1f1", "r5i1p1f1"]``."""
        body = {
            "collections": [self.collection],
            "filter-lang": "cql2-json",
            "filter": self._cql2(filters),
            "limit": page_size,
        }
        items: list[StacItem] = []
        while True:
            resp = self._http.post(f"{self.url}/search", json=body)
            resp.raise_for_status()
            page = resp.json()
            items += [StacItem(f["id"], f["properties"], f.get("assets", {})) for f in page["features"]]
            nxt = [link for link in page.get("links", []) if link.get("rel") == "next"]
            if not nxt or not page["features"] or len(items) >= cap:
                return items
            body = {**body, **nxt[0].get("body", {})}

    # -- download --------------------------------------------------------

    def download(self, item: StacItem, verbose: bool = True) -> list[Path]:
        """Download an item's files into the cache, resuming partial ones.

        Files are laid out under the cache by DRS id, so a re-run of a script
        re-uses whatever is already there.
        """
        dest_dir = self.cache_dir / item.id
        dest_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for name, url, expected in item.files():
            dest = dest_dir / name
            have = dest.stat().st_size if dest.exists() else 0
            if expected and have == expected:
                paths.append(dest)
                continue
            if have and not expected:  # can't verify; trust what we have
                paths.append(dest)
                continue
            if verbose:
                what = "resuming" if have else "downloading"
                print(f"  {what} {name} ({(expected - have) / 1e6:.0f} MB)", flush=True)
            self._fetch(url, dest, have)
            got = dest.stat().st_size
            if expected and got != expected:
                raise OSError(f"{name}: got {got} bytes, expected {expected}")
            paths.append(dest)
        return paths

    def _fetch(self, url: str, dest: Path, resume_from: int) -> None:
        headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
        with self._http.stream("GET", url, headers=headers) as r:
            if resume_from and r.status_code == 200:
                resume_from = 0  # server ignored the range; start over
            elif r.status_code not in (200, 206):
                r.raise_for_status()
            with open(dest, "ab" if resume_from else "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)

    def download_all(self, items: list[StacItem], verbose: bool = True) -> dict[str, list[Path]]:
        total = sum(i.size for i in items)
        if verbose:
            print(f"{len(items)} datasets, {total / 1e9:.2f} GB total")
        out = {}
        for item in items:
            if verbose:
                print(f"- {item}", flush=True)
            out[item.id] = self.download(item, verbose=verbose)
        return out

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> StacClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def summarise(items: list[StacItem]) -> str:
    """One line per item, for the coverage checks the scripts print."""
    return "\n".join(f"  {i}  {i.size / 1e6:.0f} MB" for i in sorted(items, key=str))
