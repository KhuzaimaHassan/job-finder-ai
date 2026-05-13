from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Adzuna API credentials (register free at developer.adzuna.com)
    ADZUNA_APP_ID: Optional[str] = None
    ADZUNA_APP_KEY: Optional[str] = None

    # JSearch API via RapidAPI (free 200 req/month)
    JSEARCH_API_KEY: Optional[str] = None

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # Gemini API
    GEMINI_API_KEY: Optional[str] = None
    # Chat/completions model for ATS, cover letter, skill gap, interview prep
    GEMINI_AI_MODEL: Optional[str] = None  # defaults to ai_prompts.GEMINI_AI_MODEL_ID

    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "allow"}


settings = Settings()
