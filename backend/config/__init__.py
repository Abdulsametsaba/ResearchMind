"""
==============================================================================
ResearchMind - Konfigürasyon Modülü
==============================================================================
Bu modül, uygulamanın tüm ayarlarını ve ortam değişkenlerini dışa aktarır.
==============================================================================
"""

from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]

