from app.config.env_config import GetEnv
from app.utils.logger import logger


class CloudinaryConfig:
    _initialized: bool = False
    _health_status: bool = False

    @classmethod
    def initialize(cls):
        if cls._initialized:
            return

        import cloudinary

        cloudinary.config(
            cloud_name=GetEnv.cloudinary.cloud_name(),
            api_key=GetEnv.cloudinary.api_key(),
            api_secret=GetEnv.cloudinary.api_secret(),
            secure=True,
        )

        cls._initialized = True
        logger.info("Cloudinary initialized")

    @classmethod
    async def health_check(cls) -> bool:
        try:
            import cloudinary.api

            # Ensure configuration is initialized
            if not cls._initialized:
                cls.initialize()

            # Cloudinary Python SDK is sync → wrap if using async frameworks
            cloudinary.api.ping()
            cls._health_status = True
            return True
        except Exception as e:
            logger.error(f"Cloudinary health check failed: {e}")
            cls._health_status = False
            return False

    @classmethod
    def is_healthy(cls) -> bool:
        """Sync method to check cached health status without awaiting."""
        return cls._health_status

    @classmethod
    async def shutdown(cls):
        # No real connection to close (same as TS)
        logger.info("Cloudinary shutdown (no-op)")


# Export-style usage
cloudinary_instance = None
