from pydantic_settings import BaseSettings
from pydantic import Field
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
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    MATCH_CANDIDATE_LIMIT: int = Field(100, ge=1, le=100)
    MATCH_TIMEOUT_SECONDS: float = Field(20.0, gt=0, le=40)
    JOB_CACHE_MAX_AGE_DAYS: int = Field(14, ge=1)
    JOB_POSTED_MAX_AGE_DAYS: int = Field(30, ge=1, le=365)
    JOB_PROVIDER_MAX_PAGES: int = Field(5, ge=1, le=20)
    JOB_REFRESH_TIMEOUT_SECONDS: int = Field(240, ge=30, le=480)

    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "allow"}


settings = Settings()
