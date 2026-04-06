"""
Core Interfaces Module
"""

from .connectors import (
    APISourceConfig,
    DatabaseSourceConfig,
    DataRecord,
    DataSourceConfig,
    DataTransformationType,
    ETLPipelineConfig,
    ExtractionResult,
    FileSourceConfig,
    IAPIConnector,
    IDatabaseConnector,
    IDataLoader,
    IDataSourceConnector,
    IDataTransformer,
    IETLPipeline,
    IFileConnector,
    TransformationRule,
)
from .erp import (
    ConnectorInfo,
    ERPCustomer,
    ERPInvoice,
    ERPPayment,
    IERPConnector,
    SyncDirection,
    SyncResult,
)
from .messaging import (
    IMessagingProvider,
    MessageStatus,
    ProviderInfo,
    SendResult,
    StatusResult,
)
from .repository import (
    IAggregateRepository,
    ICacheService,
    IEventPublisher,
    IEventSubscriber,
    IRepository,
    ITenantRepository,
    IUnitOfWork,
)

__all__ = [
    # Repository interfaces
    "IRepository",
    "ITenantRepository",
    "IAggregateRepository",
    "IUnitOfWork",
    "IEventPublisher",
    "IEventSubscriber",
    "ICacheService",
    # Connector interfaces
    "IDataSourceConnector",
    "IFileConnector",
    "IDatabaseConnector",
    "IAPIConnector",
    "IDataTransformer",
    "IDataLoader",
    "IETLPipeline",
    # Messaging interfaces
    "IMessagingProvider",
    "MessageStatus",
    "ProviderInfo",
    "SendResult",
    "StatusResult",
    # ERP/CRM interfaces
    "IERPConnector",
    "ConnectorInfo",
    "ERPInvoice",
    "ERPPayment",
    "ERPCustomer",
    "SyncDirection",
    "SyncResult",
    # Config classes
    "DataSourceConfig",
    "FileSourceConfig",
    "DatabaseSourceConfig",
    "APISourceConfig",
    "ETLPipelineConfig",
    "TransformationRule",
    "DataTransformationType",
    # Data classes
    "DataRecord",
    "ExtractionResult",
]

