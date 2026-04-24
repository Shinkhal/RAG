import os
import sys
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - production can provide env vars directly
    def load_dotenv() -> None:  # type: ignore[no-redef]
        return None


load_dotenv()


# =====================================
# HELPERS
# =====================================

def required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"❌ Missing environment variable: {key}")
    return value


def optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def number(key: str, default: Optional[int] = None) -> int:
    raw = os.getenv(key)

    if raw is None:
        if default is not None:
            return default
        raise ValueError(f"❌ Missing environment variable: {key}")

    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"❌ {key} must be a number")


def optional_number(key: str) -> Optional[int]:
    raw = os.getenv(key)
    if raw is None:
        return None

    try:
        return int(raw)
    except ValueError:
        return None


# =====================================
# ENV CONFIG
# =====================================

class GetEnv:

    # ---------- APP ----------
    class app:
        @staticmethod
        def env():
            return optional("APP_ENV", optional("NODE_ENV", "development"))

        @staticmethod
        def port():
            return number("PORT", 8000)

        @staticmethod
        def is_prod():
            return GetEnv.app.env() == "production"

        @staticmethod
        def is_dev():
            return not GetEnv.app.is_prod()

    # ---------- CLIENT ----------
    class client:
        @staticmethod
        def url():
            return optional("FRONTEND_URL")

    # ---------- DATABASE ----------
    class database:
        @staticmethod
        def url():
            database_url = optional("DATABASE_URL")
            if database_url:
                return database_url

            raise ValueError("❌ DATABASE_URL must be set")

        @staticmethod
        def source() -> str:
            database_url = optional("DATABASE_URL")
            if database_url:
                return "DATABASE_URL"

            return "missing"


    # ---------- REDIS ----------
    class redis:
        @staticmethod
        def url():
            return optional("UPSTASH_REDIS_REST_URL") or optional("REDIS_URL")

        @staticmethod
        def token():
            return optional("UPSTASH_REDIS_REST_TOKEN") or optional("REDIS_TOKEN")

    # ---------- BACKEND ----------
    class backend:
        @staticmethod
        def public_url():
            return optional("BACKEND_PUBLIC_URL")



    # ---------- CLOUDINARY ----------
    class cloudinary:
        @staticmethod
        def cloud_name():
            return optional("CLOUDINARY_CLOUD_NAME")

        @staticmethod
        def api_key():
            return optional("CLOUDINARY_API_KEY")

        @staticmethod
        def api_secret():
            return optional("CLOUDINARY_API_SECRET")

    # =====================================
    # VALIDATION
    # =====================================

    @staticmethod
    def validate():
        print("🔍 Validating environment...")

        try:
            GetEnv.database.url()
            print("✅ Env validation passed")
        except Exception as e:
            print("❌ Env validation failed:")
            print(str(e))
            sys.exit(1)


# =====================================
# AUTO VALIDATE (PROD)
# =====================================

if GetEnv.app.is_prod():
    GetEnv.validate()


class EnvSettings:
    class _AppNamespace:
        def env(self) -> str:
            return GetEnv.app.env()

        def port(self) -> int:
            return GetEnv.app.port()

        def is_prod(self) -> bool:
            return GetEnv.app.is_prod()

        def is_dev(self) -> bool:
            return GetEnv.app.is_dev()

    class _DatabaseNamespace:
        def url(self) -> str:
            return GetEnv.database.url()

        def source(self) -> str:
            return GetEnv.database.source()

    class _RedisNamespace:
        def url(self) -> str:
            return GetEnv.redis.url()

        def token(self) -> str:
            return GetEnv.redis.token()

    class _CloudinaryNamespace:
        def cloud_name(self) -> str:
            return GetEnv.cloudinary.cloud_name()

        def api_key(self) -> str:
            return GetEnv.cloudinary.api_key()

        def api_secret(self) -> str:
            return GetEnv.cloudinary.api_secret()

    @property
    def app(self) -> "EnvSettings._AppNamespace":
        return EnvSettings._AppNamespace()

    @property
    def database(self) -> "EnvSettings._DatabaseNamespace":
        return EnvSettings._DatabaseNamespace()

    @property
    def redis(self) -> "EnvSettings._RedisNamespace":
        return EnvSettings._RedisNamespace()

    @property
    def cloudinary(self) -> "EnvSettings._CloudinaryNamespace":
        return EnvSettings._CloudinaryNamespace()

    @property
    def app_env(self) -> str:
        return GetEnv.app.env()

    @property
    def is_production(self) -> bool:
        return GetEnv.app.is_prod()

    @property
    def database_url(self) -> str:
        return GetEnv.database.url()

    @property
    def resolved_database_url(self) -> str:
        return self.database_url

    @property
    def database_url_source(self) -> str:
        return GetEnv.database.source()

    @property
    def gemini_api_key(self) -> str:
        return optional("GEMINI_API_KEY")

    @property
    def openai_api_key(self) -> str:
        return optional("OPENAI_API_KEY")

    @property
    def openai_base_url(self) -> str:
        return optional("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @property
    def anthropic_api_key(self) -> str:
        return optional("ANTHROPIC_API_KEY")

    @property
    def anthropic_base_url(self) -> str:
        return optional("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")

    @property
    def r2_account_id(self) -> str:
        return optional("R2_ACCOUNT_ID")

    @property
    def r2_access_key_id(self) -> str:
        return optional("R2_ACCESS_KEY_ID")

    @property
    def r2_secret_access_key(self) -> str:
        return optional("R2_SECRET_ACCESS_KEY")

    @property
    def r2_bucket_name(self) -> str:
        return optional("R2_BUCKET_NAME", "documents")

    @property
    def r2_endpoint(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def redis_url(self) -> str:
        return optional("REDIS_URL", "redis://localhost:6379")

    @property
    def redis_token(self) -> str:
        return optional("REDIS_TOKEN")

    @property
    def redis_rest_url(self) -> str:
        return optional("UPSTASH_REDIS_REST_URL")

    @property
    def redis_rest_token(self) -> str:
        return optional("UPSTASH_REDIS_REST_TOKEN")

    @property
    def query_cache_ttl_seconds(self) -> int:
        return number("QUERY_CACHE_TTL_SECONDS", 3600)

    @property
    def free_tier_model(self) -> str:
        return optional("FREE_TIER_MODEL", "gemini-2.0-flash")

    @property
    def pro_tier_model(self) -> str:
        return optional("PRO_TIER_MODEL", "gpt-4o-mini")

    @property
    def enterprise_tier_model(self) -> str:
        return optional("ENTERPRISE_TIER_MODEL", "claude-3-5-sonnet-20241022")

    @property
    def max_chunk_size(self) -> int:
        return number("MAX_CHUNK_SIZE", 512)

    @property
    def chunk_overlap(self) -> int:
        return number("CHUNK_OVERLAP", 64)

    @property
    def embedding_batch_size(self) -> int:
        return number("EMBEDDING_BATCH_SIZE", 32)

    @property
    def embedding_model(self) -> str:
        return optional("EMBEDDING_MODEL", "gemini-embedding-001")

    @property
    def embedding_output_dimensionality(self) -> int:
        return number("EMBEDDING_OUTPUT_DIMENSIONALITY", 768)

    @property
    def default_top_k(self) -> int:
        return number("DEFAULT_TOP_K", 5)

    @property
    def min_retrieval_score(self) -> float:
        raw = optional("MIN_RETRIEVAL_SCORE", "0.7")
        return float(raw)

    @property
    def log_level(self) -> str:
        return optional("LOG_LEVEL", "INFO")

    @property
    def max_pdf_size_mb(self) -> int:
        return number("MAX_PDF_SIZE_MB", 10)

    @property
    def max_pdf_uploads_per_hour(self) -> int:
        return number("MAX_PDF_UPLOADS_PER_HOUR", 20)

def get_settings() -> EnvSettings:
    """Return the shared env accessor used by the app."""
    return EnvSettings()


def get_env() -> GetEnv:
    """Return the shared env accessor used by legacy config modules."""
    return GetEnv
