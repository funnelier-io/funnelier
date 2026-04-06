"""
ERP Connector Registry — factory for getting the configured connector.
"""

import logging
from functools import lru_cache

from src.core.config import get_settings
from src.core.interfaces.erp import IERPConnector

logger = logging.getLogger(__name__)

_CONNECTORS: dict[str, type] = {}


def _register_builtins() -> None:
    """Lazy-register built-in connectors."""
    global _CONNECTORS
    if _CONNECTORS:
        return

    from .mock_adapter import MockERPAdapter
    _CONNECTORS["mock"] = MockERPAdapter

    try:
        from .mongodb_adapter import MongoDBERPAdapter
        _CONNECTORS["mongodb"] = MongoDBERPAdapter
    except ImportError:
        pass

    try:
        from .odoo_adapter import OdooERPAdapter
        _CONNECTORS["odoo"] = OdooERPAdapter
    except ImportError:
        pass


class ERPConnectorRegistry:
    """
    Factory that returns the configured IERPConnector instance.

    The connector is selected by the ERP_PROVIDER env var (default: "mock").
    """

    @staticmethod
    @lru_cache
    def get() -> IERPConnector:
        _register_builtins()
        settings = get_settings()
        provider_name = getattr(settings, "erp_provider", "mock")

        if provider_name == "mongodb":
            mongo = settings.mongodb
            if mongo.url:
                from .mongodb_adapter import MongoDBERPAdapter
                logger.info("Using MongoDB ERP connector")
                return MongoDBERPAdapter(url=mongo.url, database=mongo.database)
            else:
                logger.warning("MongoDB URL not set, falling back to mock ERP")
                provider_name = "mock"

        if provider_name == "odoo":
            odoo = getattr(settings, "odoo", None)
            if odoo and getattr(odoo, "url", ""):
                from .odoo_adapter import OdooERPAdapter
                logger.info("Using Odoo ERP connector")
                return OdooERPAdapter(
                    url=odoo.url, db=odoo.db,
                    username=odoo.username, password=odoo.password,
                )
            else:
                logger.warning("Odoo settings not configured, falling back to mock ERP")
                provider_name = "mock"

        if provider_name == "mock" or provider_name not in _CONNECTORS:
            from .mock_adapter import MockERPAdapter
            logger.info("Using Mock ERP connector")
            return MockERPAdapter()

        cls = _CONNECTORS[provider_name]
        return cls()

    @staticmethod
    def register(name: str, connector_class: type) -> None:
        """Register a custom connector at runtime."""
        _CONNECTORS[name] = connector_class

    @staticmethod
    def available() -> list[str]:
        """List available connector names."""
        _register_builtins()
        return list(_CONNECTORS.keys())

