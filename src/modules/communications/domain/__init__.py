"""
Communications Module - Domain Layer
"""

from .entities import CallLog, SMSLog, SMSTemplate
from .repositories import ICallLogRepository, ISMSLogRepository, ISMSTemplateRepository

__all__ = [
    "SMSTemplate",
    "SMSLog",
    "CallLog",
    "ISMSLogRepository",
    "ICallLogRepository",
    "ISMSTemplateRepository",
]

