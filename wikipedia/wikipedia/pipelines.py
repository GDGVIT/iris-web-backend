# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import sqlite3

class WikipediaPipeline:
    def __init__(self):
        self.create_connection()
        self.create_table()

    def create_connection(self):
        self.conn = sqlite3.connect("links.db")
        self.curr = self.conn.cursor()

    def create_table(self):
        self.curr.execute("""drop table if exists links""")
        self.curr.execute("""create table links(
                                  name text,
                                  link text)
                                  """)

    def store_db(self, item):
        self.curr.execute("""insert into links values(?,?)""", (
            item['name'],
            item['link']
        ))
        self.conn.commit()

    def process_item(self, item, _spider):
        self.store_db(item)
        return item