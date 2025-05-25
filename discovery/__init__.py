# discovery/__init__.py

# must come before any Twisted imports!
from scrapy.utils.reactor import install_reactor
install_reactor('twisted.internet.asyncioreactor.AsyncioSelectorReactor')
