"""Run discovery for a city: queries -> hits -> normalized, deduplicated, filtered URLs."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from travel_scraper.discovery.base import DiscoveryError, SearchProvider
from travel_scraper.discovery.urls import dedupe_key, eligibility, normalize_url
from travel_scraper.handoff import now

log = logging.getLogger(__name__)

QUERY_TEMPLATES: dict[str, tuple[str, ...]] = {
    "attractions": ("{city} {country} top tourist attractions",
                    "{city} {country} landmarks official website"),
    "museums": ("{city} {country} museums official website",),
    "restaurants": ("{city} {country} restaurants", "{city} {country} vegetarian restaurants"),
    "activities": ("{city} {country} things to do", "{city} {country} outdoor activities"),
    "nightlife": ("{city} {country} bars nightlife",),
    "shopping": ("{city} {country} shopping markets",),
}  # fmt: skip
CATEGORIES = tuple(QUERY_TEMPLATES)


def build_queries(city: str, country: str, categories: list[str]) -> list[tuple[str, str]]:
    """(category, query) pairs. Unknown categories raise ValueError."""
    unknown = [c for c in categories if c not in QUERY_TEMPLATES]
    if unknown:
        raise ValueError(f"unknown categories {unknown}; choose from {', '.join(CATEGORIES)}")
    return [
        (category, template.format(city=city, country=country))
        for category in categories
        for template in QUERY_TEMPLATES[category]
    ]


@dataclass
class DiscoveredUrl:
    url: str
    query: str
    category: str
    provider: str
    discovered_at: datetime
    eligible: bool
    reason: str
    priority: int
    title: str = ""

    def to_json(self) -> str:
        data = asdict(self)
        data["discovered_at"] = self.discovered_at.isoformat()
        return json.dumps(data, ensure_ascii=False)


@dataclass
class DiscoveryResult:
    city: str
    country: str
    urls: list[DiscoveredUrl] = field(default_factory=list)
    failed_queries: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> list[DiscoveredUrl]:
        return sorted((u for u in self.urls if u.eligible), key=lambda u: (u.priority, u.url))

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(u.to_json() + "\n" for u in self.urls), encoding="utf-8")
        return path


def discover(
    city: str,
    country: str,
    categories: list[str],
    provider: SearchProvider,
    *,
    max_results: int = 10,
) -> DiscoveryResult:
    """Never raises for a failed search: the query is recorded and skipped."""
    result = DiscoveryResult(city=city, country=country)
    seen: set[str] = set()
    for category, query in build_queries(city, country, categories):
        try:
            hits = provider.search(query, max_results)
        except DiscoveryError as exc:
            log.warning("search failed for %r: %s", query, exc)
            result.failed_queries.append(f"{query}: {exc}")
            continue
        for hit in hits:
            url = normalize_url(hit.url)
            if url is None or dedupe_key(url) in seen:
                continue
            seen.add(dedupe_key(url))
            check = eligibility(url)
            result.urls.append(
                DiscoveredUrl(
                    url=url,
                    query=query,
                    category=category,
                    provider=provider.name,
                    discovered_at=now(),
                    eligible=check.eligible,
                    reason=check.reason,
                    priority=check.priority,
                    title=hit.title,
                )
            )
    return result


def read_discovered(path: Path) -> list[DiscoveredUrl]:
    rows: list[DiscoveredUrl] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            data = json.loads(line)
            data["discovered_at"] = datetime.fromisoformat(data["discovered_at"])
            rows.append(DiscoveredUrl(**data))
    return rows
