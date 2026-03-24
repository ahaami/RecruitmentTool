"""Recruitment agency detection and filtering.

Identifies and filters out recruitment agencies, staffing firms, and
job board companies from discovery results. These are competitors,
not potential clients.
"""

import re

# Known recruitment agency keywords in company names
AGENCY_KEYWORDS = [
    "recruitment",
    "recruiting",
    "recruiter",
    "staffing",
    "talent acquisition",
    "talent solutions",
    "talent partners",
    "talent international",
    "talent specialist",
    "headhunt",
    "head hunt",
    "executive search",
    "employment agency",
    "employment services",
    "job board",
    "career",
    "human resources consulting",
    "hr consulting",
    "contracting",
    "contractors",
    "labour hire",
    "labor hire",
    "temp agency",
    "temporary staffing",
    "workforce solutions",
    "workforce management",
    "people solutions",
    "resourcing",
]

# Known Australian recruitment agencies (exact or partial name matches)
KNOWN_AGENCIES = [
    "hays",
    "randstad",
    "robert half",
    "robert walters",
    "michael page",
    "page group",
    "pagegroup",
    "hudson",
    "adecco",
    "manpower",
    "manpowergroup",
    "chandler macleod",
    "programmed",
    "peoplebank",
    "clicks it recruitment",
    "paxus",
    "finite it",
    "talent international",
    "talent – specialists",
    "talent specialists",
    "talentinternational",
    "clarius",
    "ambition",
    "hatch",
    "aurec",
    "davidson",
    "davidson technology",
    "recruit it",
    "recruitit",
    "lime recruitment",
    "recruitment hive",
    "candle",
    "modis",
    "akkodis",
    "experis",
    "greythorn",
    "peopleconnect",
    "people2people",
    "hamilton james",
    "hamilton james & bruce",
    "spring professional",
    "seek",
    "indeed",
    "linkedin",
    "jora",
    "glassdoor",
    "ziprecruiter",
    "adzuna",
    "careerone",
    "ethical jobs",
    "jobadder",
    "jobactive",
    "employment hero",
    "expr3ss",
    "shortlyster",
    "sharp & carter",
    "sharp and carter",
    "talent & recruitment",
    "u&u",
    "u & u",
    "charterhouse",
    "bluefin resources",
    "halcyon knights",
    "ignite",
    "ajilon",
    "kelly services",
    "hender consulting",
    "frog recruitment",
    "future you",
    "futureyou",
    "eighty20",
    "eighty 20",
    "mcarthur",
    "humanis",
    "evolved people",
    "six degrees",
    "six degrees executive",
    "talent army",
    "specsolutions",
    "infotech",
]


def is_recruitment_agency(company_name: str) -> bool:
    """Check if a company name looks like a recruitment agency.

    Args:
        company_name: The company name to check.

    Returns:
        True if the company appears to be a recruitment agency.
    """
    name_lower = company_name.lower().strip()

    # Check against known agencies
    for agency in KNOWN_AGENCIES:
        if agency in name_lower:
            return True

    # Check for agency keywords
    for keyword in AGENCY_KEYWORDS:
        if keyword in name_lower:
            return True

    # Check for patterns like "X Recruitment" or "X Staffing"
    agency_suffix_pattern = r"\b(?:recruitment|recruiting|staffing|resourcing)\s*(?:group|agency|services|solutions|pty|ltd)?\.?\s*$"
    if re.search(agency_suffix_pattern, name_lower):
        return True

    return False


def filter_agencies(companies: list[dict], name_key: str = "name") -> tuple[list[dict], list[dict]]:
    """Split a list of companies into non-agencies and agencies.

    Args:
        companies: List of company dicts.
        name_key: Key in dict containing the company name.

    Returns:
        Tuple of (real_companies, agencies).
    """
    real = []
    agencies = []

    for company in companies:
        name = company.get(name_key, "")
        if is_recruitment_agency(name):
            agencies.append(company)
        else:
            real.append(company)

    return real, agencies
