"""Modular template system for autowebdelivery.

Decomposes Stitch-generated HTML templates into composable, data-driven modules.
Supports 4 template families: clinical-trust, warm-editorial, industrial-reliable, fresh-utility.
"""

from .parser import TemplateParser
from .composer import TemplateComposer
from .models import BusinessData, ServiceItem, HoursSchedule

__all__ = ["TemplateParser", "TemplateComposer", "BusinessData", "ServiceItem", "HoursSchedule"]
