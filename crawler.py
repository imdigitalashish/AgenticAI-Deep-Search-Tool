from crawl4ai import *
import asyncio
from utils import scrape_duckduckgo_content
import os
import uuid
from sentence_transformers import SentenceTransformer
import chromadb


class DeepSearchPipeline:

    def __init__(self, query):
        self.query = query
        self.links = []
        self.knowledge_base_directory = str(uuid.uuid4())
        self.scrape_all_contents()
        self.crawl_and_create_repo()
        self.setup_vector_db()

    def scrape_all_contents(self):
        self.links = scrape_duckduckgo_content(self.query, 1)

    def crawl_and_create_repo(self):

        
        os.makedirs(self.knowledge_base_directory)

        async def crawl():
            async with AsyncWebCrawler() as crawler:
                for link in self.links:
                    result = await crawler.arun(
                        url=link
                    ) 

                    f = open(f"{self.knowledge_base_directory}/{self.links.index(link)}.md", "w+")
                    f.write(result.markdown)
                    f.close()
        asyncio.run(crawl())

    def setup_vector_db(self):
        self.embedding_model = SentenceTransformer('all-mpnet-base-v2')

        # Initialize ChromaDB client and collection
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.create_collection(name="knowledge_base")

        # Process and store embeddings
        for filename in os.listdir(self.knowledge_base_directory):
            if filename.endswith(".md"):
                filepath = os.path.join(self.knowledge_base_directory, filename)
                with open(filepath, "r") as f:
                    content = f.read()

                # Generate embedding for the content
                embedding = self.embedding_model.encode(content).tolist()

                # Add embedding to ChromaDB
                self.collection.add(
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[{"source": filename}],
                    ids=[filename]
                )
    def query_vector_db(self, query_text, n_results=2):
        # Generate embedding for the query
        query_embedding = self.embedding_model.encode(query_text).tolist()

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        return results


deepSearch = DeepSearchPipeline("Python")


query_results = deepSearch.query_vector_db("When python was released?")
print(deepSearch.links)