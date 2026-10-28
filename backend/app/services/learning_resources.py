"""Reviewed publisher resources. Never publish a model-invented course URL."""
import re

RESOURCES = (
    (r"python", "The Python Tutorial", "Python", "https://docs.python.org/3/tutorial/"),
    (r"sql|postgres|database", "PostgreSQL and SQL Tutorial", "PostgreSQL", "https://www.postgresql.org/docs/current/tutorial.html"),
    (r"docker|container", "Get started with Docker", "Docker", "https://docs.docker.com/get-started/"),
    (r"fastapi|rest api", "FastAPI Tutorial", "FastAPI", "https://fastapi.tiangolo.com/tutorial/"),
    (r"machine learning|deep learning|pytorch", "Practical Deep Learning for Coders", "fast.ai", "https://course.fast.ai/"),
    (r"nlp|llm|transformer|hugging", "LLM Course", "Hugging Face", "https://huggingface.co/learn/llm-course/chapter1/1"),
)


def for_skills(skills: list[str]) -> list[dict]:
    text = " ".join(skills).lower()
    return [{"name": name, "platform": platform, "url": url, "free": True}
            for pattern, name, platform, url in RESOURCES if re.search(r"\b(?:" + pattern + r")\b", text)]
