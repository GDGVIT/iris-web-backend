import wikipedia.spiders.index_scraper as index_scraper
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
import wikipedia.settings as my_settings

crawler_settings = Settings()
crawler_settings.setmodule(my_settings)
process = CrawlerProcess(settings=crawler_settings)
process.crawl(index_scraper.IndexScraper)
process.start()
