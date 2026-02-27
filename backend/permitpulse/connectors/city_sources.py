from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class RawRuleDocument:
    city_code: str
    source_url: str
    content: str


CITY_SOURCES = {
    "NYC": "https://www.nyc.gov/site/specialenforcement/registration-law/registration-for-hosts.page",
    "LA": "https://planning.lacity.gov/plans-policies/initiatives-policies/home-sharing",
    "SF": "https://www.sf.gov/short-term-rentals",
}


def fetch_city_document(city_code: str, timeout: int = 15) -> RawRuleDocument:
    source_url = CITY_SOURCES[city_code]
    response = requests.get(source_url, timeout=timeout)
    response.raise_for_status()
    return RawRuleDocument(city_code=city_code, source_url=source_url, content=response.text)
