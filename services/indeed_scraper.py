"""Indeed AU job discovery via Google News RSS fallback.

Direct scraping of Indeed is blocked (403). Instead, we use Google
to search for Indeed AU IT job listings, which gives us company names
from recent postings.
"""

import feedparser
import re
import time
from dataclasses import dataclass, field

import config


@dataclass
class IndeedCompany:
    """A company found via Indeed AU with IT job postings."""
    name: str
    job_count: int
    job_titles: list[str] = field(default_factory=list)
    city: str = ""
    state: str = ""


CITY_TO_STATE = {
    "Sydney": "NSW",
    "Melbourne": "VIC",
    "Brisbane": "QLD",
    "Perth": "WA",
    "Canberra": "ACT",
}

# IT-related search terms
IT_SEARCH_TERMS = [
    "software engineer",
    "IT manager",
    "devops engineer",
    "data engineer",
    "cybersecurity analyst",
    "cloud engineer",
]


def _search_google_for_indeed(query: str) -> list[dict]:
    """Search Google News RSS for Indeed AU job listings."""
    rss_url = (
        "https://news.google.com/rss/search?"
        f"q={query.replace(' ', '+')}&hl=en-AU&gl=AU&ceid=AU:en"
    )

    jobs = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:15]:
            title = entry.get("title", "")
            # Common Indeed title formats:
            # "Job Title - Company Name - City" or "Job Title | Company Name"
            company = ""
            job_title = ""

            if " - " in title:
                parts = [p.strip() for p in title.split(" - ")]
                if len(parts) >= 2:
                    job_title = parts[0]
                    company = parts[1]
            elif " | " in title:
                parts = [p.strip() for p in title.split(" | ")]
                if len(parts) >= 2:
                    job_title = parts[0]
                    company = parts[1]

            # Clean company name — remove trailing location info
            company = re.sub(r"\s*[-–]\s*(Sydney|Melbourne|Brisbane|Perth|Canberra|Adelaide).*$", "", company)
            company = re.sub(r"\s*\d+\.\d+$", "", company)  # Remove rating numbers

            if company and len(company) > 2 and len(company) < 60:
                jobs.append({
                    "title": job_title,
                    "company": company,
                })
    except Exception:
        pass

    return jobs


def scrape_indeed_it_jobs(
    cities: list[str] | None = None,
    searches_per_city: int = 2,
    delay: float = 2.0,
) -> list[IndeedCompany]:
    """Find IT companies posting on Indeed AU via Google search.

    Args:
        cities: List of AU cities to search. Defaults to config.TARGET_CITIES.
        searches_per_city: Number of IT search terms per city.
        delay: Seconds between requests.

    Returns:
        List of IndeedCompany objects, sorted by job_count descending.
    """
    if cities is None:
        cities = config.TARGET_CITIES

    all_jobs: list[dict] = []

    for city in cities:
        state = CITY_TO_STATE.get(city, "")

        for term in IT_SEARCH_TERMS[:searches_per_city]:
            query = f"site:au.indeed.com {term} {city}"
            jobs = _search_google_for_indeed(query)

            for job in jobs:
                job["search_city"] = city
                job["search_state"] = state

            all_jobs.extend(jobs)
            print(f"  Indeed {city} '{term}': {len(jobs)} jobs found")
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
        companies.append(IndeedCompany(
            name=jobs[0]["company"],
            job_count=len(jobs),
            job_titles=list({j["title"] for j in jobs if j["title"]}),
            city=jobs[0].get("search_city", ""),
            state=jobs[0].get("search_state", ""),
        ))

    companies.sort(key=lambda c: c.job_count, reverse=True)
    return companies
