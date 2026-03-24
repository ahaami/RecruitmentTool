"""Seek.com.au job discovery via Seek's v5 search API.

Uses Seek's public job search API (v5) to find IT job postings in
Australian cities. Groups results by company to identify companies
with multiple open IT roles — a strong hiring signal.
"""

import httpx
import time
from dataclasses import dataclass, field

import config


@dataclass
class SeekCompany:
    """A company found on Seek with IT job postings."""
    name: str
    job_count: int
    job_titles: list[str] = field(default_factory=list)
    city: str = ""
    state: str = ""
    seek_url: str = ""


CITY_TO_STATE = {
    "Sydney": "NSW",
    "Melbourne": "VIC",
    "Brisbane": "QLD",
    "Perth": "WA",
    "Canberra": "ACT",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Working Seek search API endpoint
SEEK_API_URL = "https://www.seek.com.au/api/jobsearch/v5/search"


def _fetch_seek_page(client: httpx.Client, city: str, page: int = 1) -> list[dict]:
    """Fetch a page of IT jobs from Seek's v5 API."""
    params = {
        "where": city,
        "classification": "6281",  # Information & Communication Technology
        "page": str(page),
        "pageSize": "30",
        "sortmode": "ListedDate",
    }

    resp = client.get(SEEK_API_URL, params=params)
    if resp.status_code != 200:
        return []

    data = resp.json()
    jobs = []
    for item in data.get("data", []):
        advertiser = item.get("advertiser", {})
        company = advertiser.get("description", "") or advertiser.get("name", "")
        title = item.get("title", "")
        location = item.get("location", "")

        if company:
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
            })

    return jobs


def scrape_seek_it_jobs(
    cities: list[str] | None = None,
    pages_per_city: int = 3,
    delay: float = 2.0,
) -> list[SeekCompany]:
    """Fetch Seek IT job postings, grouped by company.

    Args:
        cities: List of AU cities to search. Defaults to config.TARGET_CITIES.
        pages_per_city: Number of pages per city (30 jobs per page).
        delay: Seconds between requests.

    Returns:
        List of SeekCompany objects, sorted by job_count descending.
    """
    if cities is None:
        cities = config.TARGET_CITIES

    all_jobs: list[dict] = []

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        for city in cities:
            state = CITY_TO_STATE.get(city, "")

            for page in range(1, pages_per_city + 1):
                jobs = _fetch_seek_page(client, city, page)
                for job in jobs:
                    job["search_city"] = city
                    job["search_state"] = state
                all_jobs.extend(jobs)
                print(f"  Seek {city} page {page}: {len(jobs)} jobs found")

                if len(jobs) == 0:
                    break  # No more results

                time.sleep(delay)

    # Group by company (normalised)
    grouped: dict[str, list[dict]] = {}
    for job in all_jobs:
        key = job["company"].lower().strip()
        if not key:
            continue
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(job)

    companies = []
    for key, jobs in grouped.items():
        company_name = jobs[0]["company"]
        companies.append(SeekCompany(
            name=company_name,
            job_count=len(jobs),
            job_titles=list({j["title"] for j in jobs if j["title"]}),
            city=jobs[0].get("search_city", ""),
            state=jobs[0].get("search_state", ""),
            seek_url=f"https://www.seek.com.au/jobs?keywords={company_name.replace(' ', '+')}&classification=6281",
        ))

    companies.sort(key=lambda c: c.job_count, reverse=True)
    return companies
