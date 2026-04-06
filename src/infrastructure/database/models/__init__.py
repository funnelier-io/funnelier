"""
SQLAlchemy Database Models
"""
from .tenants import (
    TenantModel,
    TenantUserModel,
    SalespersonModel,
    DataSourceConnectionModel,
)
from .leads import (
    LeadCategoryModel,
    LeadSourceModel,
    ContactModel,
)
from .communications import (
    SMSTemplateModel,
    SMSLogModel,
    CallLogModel,
)
from .sales import (
    ProductModel,
    ProductPriceModel,
    InvoiceModel,
    InvoiceLineItemModel,
    PaymentModel,
)
from .analytics import (
    FunnelSnapshotModel,
    AlertRuleModel,
    AlertInstanceModel,
)
from .etl import (
    ImportLogModel,
)
from .campaigns import (
    CampaignModel,
    CampaignRecipientModel,
)
from .sync import (
    SyncLogModel,
)

__all__ = [
    # Tenants
    "TenantModel",
    "TenantUserModel",
    "SalespersonModel",
    "DataSourceConnectionModel",
    # Leads
    "LeadCategoryModel",
    "LeadSourceModel",
    "ContactModel",
    # Communications
    "SMSTemplateModel",
    "SMSLogModel",
    "CallLogModel",
    # Sales
    "ProductModel",
    "ProductPriceModel",
    "InvoiceModel",
    "InvoiceLineItemModel",
    "PaymentModel",
    # Analytics
    "FunnelSnapshotModel",
    "AlertRuleModel",
    "AlertInstanceModel",
    # ETL
    "ImportLogModel",
    # Campaigns
    "CampaignModel",
    "CampaignRecipientModel",
    # Sync
    "SyncLogModel",
]

