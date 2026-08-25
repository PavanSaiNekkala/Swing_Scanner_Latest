"""
News Providers.
"""

from .google_rss_provider import GoogleRSSProvider
from .newsapi_provider import NewsAPIProvider

__all__ = [

    "GoogleRSSProvider",

    "NewsAPIProvider",

]