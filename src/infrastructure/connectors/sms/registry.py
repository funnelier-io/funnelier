"""
Messaging Provider Registry — factory for getting the configured provider.
"""

import logging
from functools import lru_cache

from src.core.config import get_settings
from src.core.interfaces.messaging import IMessagingProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type] = {}


def _register_builtins() -> None:
    """Lazy-register built-in providers."""
    global _PROVIDERS
    if _PROVIDERS:
        return

    from .mock_provider import MockMessagingProvider
    _PROVIDERS["mock"] = MockMessagingProvider

    try:
        from .kavenegar_provider import KavenegarProvider
        _PROVIDERS["kavenegar"] = KavenegarProvider
    except ImportError:
        pass


class MessagingProviderRegistry:
    """
    Factory that returns the configured IMessagingProvider instance.

    The provider is selected by the MESSAGING_PROVIDER env var (default: "mock").
    """

    @staticmethod
    @lru_cache
    def get() -> IMessagingProvider:
        _register_builtins()
        settings = get_settings()
        provider_name = getattr(settings, "messaging_provider", "mock")

        if provider_name == "kavenegar":
            kav = settings.kavenegar
            if kav.api_key:
                from .kavenegar_provider import KavenegarProvider
                logger.info("Using Kavenegar messaging provider")
                return KavenegarProvider(api_key=kav.api_key, sender=kav.sender)
            else:
                logger.warning("Kavenegar API key not set, falling back to mock provider")
                provider_name = "mock"

        if provider_name == "mock" or provider_name not in _PROVIDERS:
            from .mock_provider import MockMessagingProvider
            logger.info("Using Mock messaging provider")
            return MockMessagingProvider()

        cls = _PROVIDERS[provider_name]
        return cls()

    @staticmethod
    def register(name: str, provider_class: type) -> None:
        """Register a custom provider at runtime."""
        _PROVIDERS[name] = provider_class

    @staticmethod
    def available() -> list[str]:
        """List available provider names."""
        _register_builtins()
        return list(_PROVIDERS.keys())

