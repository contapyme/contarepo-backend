from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://cp:password@localhost:5432/contapyme"
    # Debe coincidir con el SECRET_KEY de contapyme-backend para validar los mismos tokens
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    FRONTEND_URL: str = "http://localhost:5174"
    EXTRA_CORS_ORIGINS: str = ""

    @property
    def cors_origins(self) -> list[str]:
        origins = {
            self.FRONTEND_URL,
            "http://localhost:5174",
            "http://localhost:3001",
        }
        if self.EXTRA_CORS_ORIGINS:
            for o in self.EXTRA_CORS_ORIGINS.split(","):
                o = o.strip()
                if o:
                    origins.add(o)
        return list(origins)


settings = Settings()
