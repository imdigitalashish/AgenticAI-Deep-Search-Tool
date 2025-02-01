from crawl4ai import *

import asyncio

from utils import scrape_duckduckgo_content
import os
import uuid





class DeepSearchPipeline:

    def __init__(self, query):
        self.query = query
        self.links = []
        self.scrape_all_contents()
        self.crawl_and_create_repo()

    def scrape_all_contents(self):
        self.links = scrape_duckduckgo_content(self.query, 1)

    def crawl_and_create_repo(self):

        knowledge_base_directory = str(uuid.uuid4())
        os.makedirs(knowledge_base_directory)

        async def crawl():
            async with AsyncWebCrawler() as crawler:
                for link in self.links:
                    result = await crawler.arun(
                        url=link
                    ) 

                    f = open(f"{knowledge_base_directory}/{self.links.index(link)}.md", "w+")
                    f.write(result.markdown)
                    f.close()
        asyncio.run(crawl())

deepSearch = DeepSearchPipeline("Python")

print(deepSearch.links)