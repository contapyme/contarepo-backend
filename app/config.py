from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://cp:password@localhost:5432/contapyme"
    ALGORITHM: str = "RS256"
    PUBLIC_KEY_PATH: str = "keys/public.pem"
    # Contenido de la llave pública RSA (para producción via env vars)
    RSA_PUBLIC_KEY: str = ""
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
