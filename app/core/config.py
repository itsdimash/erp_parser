from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ERP Backend"
    APP_ENV: str = "local"
    DATABASE_NAME: str = ""
    DATABASE_HOST: str = ""
    DATABASE_USER: str = ""
    DATABASE_PASSWORD: str = ""
    DATABASE_PORT: int = 0
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()