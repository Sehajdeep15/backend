from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # WEBHOOK_SECRET is required and must be non-empty
    WEBHOOK_SECRET: str = Field(..., min_length=1)
    
    # DATABASE_URL is required (e.g., sqlite:///./app.db)
    DATABASE_URL: str = Field(...)
    
    # LOG_LEVEL defaults to INFO
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# This will raise a ValidationError and exit if required variables are missing
settings = Settings()
