"""Conservative normalization shared by fresh and persisted listings."""
import html
import re


def plain_text(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or ""))


def employment_type(value: str) -> str | None:
    text = plain_text(value).lower()
    for pattern, kind in (
        (r"\bpart[\s_-]*time\b", "parttime"),
        (r"\bfull[\s_-]*time\b", "fulltime"),
        (r"\bintern(?:ship)?\b", "internship"),
        (r"\b(?:contractor|contract|freelance)\b", "contract"),
    ):
        if re.search(pattern, text):
            return kind
    return None


def work_arrangement(text: str, default: str | None) -> str | None:
    text = plain_text(text).lower()
    # Explicit office requirements outweigh a remote board's default label.
    if re.search(r"\b(?:in[ -]office company|(?:work|working|office) (?:on[ -]site|in[ -]office)|5 days a week (?:in|at) (?:the )?office)\b", text):
        return "onsite"
    if re.search(r"\b(?:this (?:role|position) is hybrid|hybrid (?:role|position|work))\b", text):
        return "hybrid"
    return default


def contains_skill(text: str, tag: str) -> bool:
    text = plain_text(text)
    if tag == "R":
        return bool(re.search(r"(?<!\w)R(?!\w)|(?i:\brstudio\b)", text))
    if tag == "Go":
        return bool(re.search(r"(?i:\bgolang\b)|\bGo\b(?=\s*(?:[,/]|program|develop|engineer|language))", text))
    return bool(re.search(r"(?<![\w])" + re.escape(tag) + r"(?![\w])", text, re.IGNORECASE))
