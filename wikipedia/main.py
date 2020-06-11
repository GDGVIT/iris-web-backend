import wikipedia.spiders.index_scraper as index_scraper
from scrapy.crawler import CrawlerProcess

process = CrawlerProcess()
process.crawl(index_scraper.IndexScraper)
process.start()
