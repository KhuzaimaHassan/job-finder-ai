"""Shared search, freshness and matching rules. No database or provider I/O."""
from datetime import datetime, timezone, timedelta
import re
import shlex

from app.config import settings
from app.services.job_normalization import plain_text, contains_skill


def parse_date(value):
    if value is None or value == "":
        return None
    try:
        date = datetime.fromtimestamp(float(value), timezone.utc) if isinstance(value, (int, float)) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def searchable(job, now=None):
    now = now or datetime.now(timezone.utc)
    if job.availability in ("closed", "unknown"):
        return False
    if job.source == "himalayas" and not job.provider_id:
        return False  # Legacy rows must be observed with expiry/identity metadata.
    expiry = parse_date(job.expires_at)
    observed = parse_date(job.fetched_at)
    posted = parse_date(job.posted_date)
    return bool(posted and now - timedelta(days=settings.JOB_POSTED_MAX_AGE_DAYS) <= posted <= now + timedelta(days=1)
                and (not expiry or expiry > now)
                and (not observed or observed >= now - timedelta(days=settings.JOB_CACHE_MAX_AGE_DAYS)))


ALIASES = {"ai": ["AI", "artificial intelligence"], "ml": ["ML", "machine learning"],
           "machine learning": ["machine learning", "ML"],
           "artificial intelligence": ["artificial intelligence", "AI"],
           "js": ["JavaScript", "JS"], "postgres": ["Postgres", "PostgreSQL"],
           "javascript": ["JavaScript", "JS"],
           "postgresql": ["Postgres", "PostgreSQL"],
           "golang": ["Golang", "Go"], "nodejs": ["Node.js", "NodeJS"],
           "node.js": ["Node.js", "NodeJS"], "scikit-learn": ["scikit-learn", "sklearn"]}


def term_matches(text, term):
    term = term.strip()
    if not term:
        return False
    if term.lower() in ("r", "go"):
        return contains_skill(text, term.capitalize())
    candidates = ALIASES.get(term.lower(), [term])
    text = plain_text(text)
    return any(re.search(r"(?<!\w)" + r"[\s_-]+".join(re.escape(part) for part in re.split(r"[\s_-]+", candidate)) + r"(?!\w)", text, re.I)
               for candidate in candidates)


def query_terms(query):
    try:
        return shlex.split(query.strip())
    except ValueError:
        return query.strip().split()


def query_score(job, query):
    terms = query_terms(query)
    fields = [job.title, " ".join(job.tags), job.company, job.description]
    if not terms or not all(any(term_matches(text, term) for text in fields) for term in terms):
        return 0
    return sum(weight for term in terms for text, weight in zip(fields, [8, 4, 2, 1]) if term_matches(text, term))


def relevant_role(job):
    return bool(re.search(r"\b(?:engineer|developer|scientist|data|devops|mlops|programmer|architect|software|technical|analytics|machine learning)\b", job.title, re.I))


COUNTRIES = {
    "pk": ["pakistan", "pk", "karachi", "lahore", "islamabad", "rawalpindi"],
    "us": ["united states", "united states of america", "usa", "us"],
    "gb": ["united kingdom", "uk", "great britain", "england"],
    "ca": ["canada", "ca"], "in": ["india", "in"], "br": ["brazil", "br"],
    "au": ["australia", "au"], "sg": ["singapore", "sg"],
    "de": ["germany", "de"], "fr": ["france", "fr"], "es": ["spain", "es"],
}


def country_of(value):
    value = value.lower().strip()
    for code, names in COUNTRIES.items():
        if any(value == name or (len(name) > 2 and re.search(r"\b" + re.escape(name) + r"\b", value)) for name in names):
            return code
    return None


def location_eligible(job, location):
    country = country_of(location or "")
    if not country:
        return True  # Unknown geography is not proof of ineligibility.
    restrictions = job.location_restrictions
    if restrictions:
        if not any(country_of(place) == country or place.lower() in ("worldwide", "anywhere", "global") for place in restrictions):
            return False
    elif job.job_type == "remote":
        explicit = [country_of(part) for part in re.split(r"[,;/]", job.location)]
        explicit = [code for code in explicit if code]
        if explicit and country not in explicit:
            return False
        if country == "pk" and job.location.lower().strip() in ("europe", "eu", "north america", "latam", "americas"):
            return False
    elif job.job_type in ("onsite", "hybrid"):
        other = country_of(job.location)
        if other and other != country:
            return False
    if country == "pk" and job.timezone_restrictions and 300 not in job.timezone_restrictions:
        return False
    return True


def minimum_experience(job):
    text = plain_text(job.description)
    matches = re.findall(r"\b(\d{1,2})(?:\s*(?:[-–]|to)\s*\d{1,2})?\s*\+?\s*years?['’]?(?:\s+of)?\s+(?:professional\s+|relevant\s+|industry\s+|work\s+)?experience", text, re.I)
    return max((int(value) for value in matches if int(value) <= 40), default=None)
