import scrapy
from ..items import WikiItem


class WikiSpider(scrapy.Spider):
    name = 'wiki'
    allowed_domains = ["en.wikipedia.org"]
    start_urls = []

    def __init__(self, *args, **kwargs):
        super(WikiSpider, self).__init__(*args, **kwargs)
        self.start_urls = kwargs.get('start_urls').split(',')
        print(self.start_urls)
    
    def parse(self, response):
        item = WikiItem()
        page_name = response.css("p > a::text").extract()
        page_url = response.css("p > a").xpath("@href").extract()
        for (name, link) in zip(page_name, page_url):
            item['name'] = name
            item['link'] = "https://en.wikipedia.org"+link
            yield item
