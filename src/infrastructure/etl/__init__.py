"""
ETL Infrastructure Module

Provides Extract-Transform-Load capabilities for importing data from
various sources into the Funnelier system.
"""

# Extractors
from .extractors import (
    BaseExtractor,
    ExtractorRegistry,
    CSVExtractor,
    ExcelExtractor,
    JSONExtractor,
    MongoDBExtractor,
    APIExtractor,
    KavenegarExtractor,
)

# Transformers
from .transformers import (
    BaseTransformer,
    TransformerRegistry,
    CallLogTransformer,
    SMSLogTransformer,
    InvoiceTransformer,
    PaymentTransformer,
    LeadTransformer,
    PhoneNormalizer,
)

# Loaders
from .loaders import (
    BaseLoader,
    LoaderRegistry,
    LoadResult,
    DatabaseLoader,
    ContactLoader,
    CallLogLoader,
    SMSLogLoader,
    InvoiceLoader,
)

# Pipeline
from .pipeline import (
    ETLPipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStatus,
    PipelineManager,
)

# Scheduler
from .scheduler import (
    ETLScheduler,
    ScheduledJob,
    JobStatus,
    DailyScheduler,
    BatchScheduler,
)

__all__ = [
    # Extractors
    "BaseExtractor",
    "ExtractorRegistry",
    "CSVExtractor",
    "ExcelExtractor",
    "JSONExtractor",
    "MongoDBExtractor",
    "APIExtractor",
    "KavenegarExtractor",
    # Transformers
    "BaseTransformer",
    "TransformerRegistry",
    "CallLogTransformer",
    "SMSLogTransformer",
    "InvoiceTransformer",
    "PaymentTransformer",
    "LeadTransformer",
    "PhoneNormalizer",
    # Loaders
    "BaseLoader",
    "LoaderRegistry",
    "LoadResult",
    "DatabaseLoader",
    "ContactLoader",
    "CallLogLoader",
    "SMSLogLoader",
    "InvoiceLoader",
    # Pipeline
    "ETLPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStatus",
    "PipelineManager",
    # Scheduler
    "ETLScheduler",
    "ScheduledJob",
    "JobStatus",
    "DailyScheduler",
    "BatchScheduler",
]

