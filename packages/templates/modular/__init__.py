"""Modular template system for autowebdelivery.

Decomposes Stitch-generated HTML templates into composable, data-driven modules.
Supports 4 template families: clinical-trust, warm-editorial, industrial-reliable, fresh-utility.
"""

from .composer import TemplateComposer
from .models import BusinessData, HoursSchedule, ServiceItem
from .parser import TemplateParser

__all__ = ["BusinessData", "HoursSchedule", "ServiceItem", "TemplateComposer", "TemplateParser"]
