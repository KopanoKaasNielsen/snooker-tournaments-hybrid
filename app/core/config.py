from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./snooker.db"
    secret_key: str = "supersecret"
    access_token_expire_minutes: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
