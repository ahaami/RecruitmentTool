"""LinkedIn Jobs scraper.

Scrapes LinkedIn's public job search (no login required) for IT roles
in Australian cities. Groups results by company.

Note: LinkedIn aggressively rate-limits scrapers. This module uses
conservative delays and falls back gracefully on blocks.
"""

import httpx
import json
import time
from dataclasses import dataclass, field
from bs4 import BeautifulSoup

import config


@dataclass
class LinkedInCompany:
    """A company found on LinkedIn Jobs with IT job postings."""
    name: str
    job_count: int
    job_titles: list[str] = field(default_factory=list)
    city: str = ""
    state: str = ""
    linkedin_url: str = ""


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

# LinkedIn geoIds for Australian cities
CITY_GEO_IDS = {
    "Sydney": "104769905",
    "Melbourne": "100116234",
    "Brisbane": "101541851",
    "Perth": "106309714",
    "Canberra": "105765688",
}

CITY_TO_STATE = {
    "Sydney": "NSW",
    "Melbourne": "VIC",
    "Brisbane": "QLD",
    "Perth": "WA",
    "Canberra": "ACT",
}

# LinkedIn f_I (industry) codes for tech
# 4 = Computer Software, 6 = IT Services, 96 = IT & Services
IT_KEYWORDS = "software engineer OR devops OR IT OR cybersecurity OR data engineer OR cloud"


def _parse_linkedin_html(html: str) -> list[dict]:
    """Parse job listings from LinkedIn public job search HTML."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # LinkedIn public job search uses these selectors
    job_cards = soup.select(".base-card, .job-search-card")

    for card in job_cards:
        title_el = card.select_one(".base-search-card__title, h3.base-search-card__title")
        company_el = card.select_one(".base-search-card__subtitle a, h4.base-search-card__subtitle")
        location_el = card.select_one(".job-search-card__location")
        link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")

        title = title_el.get_text(strip=True) if title_el else ""
        company = company_el.get_text(strip=True) if company_el else ""
        location = location_el.get_text(strip=True) if location_el else ""
        link = link_el["href"] if link_el and link_el.has_attr("href") else ""

        if company:
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": link,
            })

    # Fallback: try JSON-LD
    if not jobs:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        org = item.get("hiringOrganization", {})
                        jobs.append({
                            "title": item.get("title", ""),
                            "company": org.get("name", ""),
                            "location": "",
                            "url": org.get("sameAs", ""),
                        })
            except (json.JSONDecodeError, TypeError):
                continue

    return jobs


def scrape_linkedin_it_jobs(
    cities: list[str] | None = None,
    results_per_city: int = 50,
    delay: float = 5.0,
) -> list[LinkedInCompany]:
    """Scrape LinkedIn Jobs for IT postings, grouped by company.

    Uses LinkedIn's public (no-auth) job search endpoint.

    Args:
        cities: List of AU cities to search. Defaults to config.TARGET_CITIES.
        results_per_city: Number of results to request per city.
        delay: Seconds between requests (LinkedIn is aggressive on rate limits).

    Returns:
        List of LinkedInCompany objects, sorted by job_count descending.
    """
    if cities is None:
        cities = config.TARGET_CITIES

    all_jobs: list[dict] = []

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        for city in cities:
            geo_id = CITY_GEO_IDS.get(city)
            if not geo_id:
                continue

            state = CITY_TO_STATE.get(city, "")

            # LinkedIn public jobs API
            url = (
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={IT_KEYWORDS.replace(' ', '%20')}"
                f"&location={city}%2C%20Australia"
                f"&geoId={geo_id}"
                f"&f_TPR=r604800"  # Past week
                f"&start=0"
                f"&count={results_per_city}"
            )

            try:
                resp = client.get(url)
                if resp.status_code == 429:
                    print(f"  LinkedIn {city}: Rate limited (429). Skipping.")
                    time.sleep(delay * 3)
                    continue
                if resp.status_code != 200:
                    print(f"  LinkedIn {city}: HTTP {resp.status_code}")
                    continue

                jobs = _parse_linkedin_html(resp.text)
                for job in jobs:
                    job["search_city"] = city
                    job["search_state"] = state

                all_jobs.extend(jobs)
                print(f"  LinkedIn {city}: {len(jobs)} jobs found")

            except httpx.HTTPError as e:
                print(f"  LinkedIn {city}: Error {e}")

            time.sleep(delay)

    # Group by company
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
        # Try to find LinkedIn company URL from job links
        linkedin_url = ""
        for j in jobs:
            if "url" in j and "linkedin.com" in j.get("url", ""):
                linkedin_url = j["url"]
                break

        companies.append(LinkedInCompany(
            name=jobs[0]["company"],
            job_count=len(jobs),
            job_titles=list({j["title"] for j in jobs if j["title"]}),
            city=jobs[0].get("search_city", ""),
            state=jobs[0].get("search_state", ""),
            linkedin_url=linkedin_url,
        ))

    companies.sort(key=lambda c: c.job_count, reverse=True)
    return companies
