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

    # URL del backend de contabanc (dominio Banca) — bank_accounts ya no vive
    # en esta misma BD desde la separación del dominio Banca (Fase 5)
    CONTABANC_URL: str = "http://localhost:8004"
    # Debe ser el mismo valor que INTERNAL_API_KEY en contabanc-backend
    INTERNAL_API_KEY: str = "change-me-generate-with-openssl-rand-hex-32"

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
