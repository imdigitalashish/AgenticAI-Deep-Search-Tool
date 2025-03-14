from playwright.sync_api import sync_playwright
from typing import List, Dict, Optional
import os
import serpapi
import uuid
import asyncio
from dotenv import load_dotenv 
from crawl4ai import AsyncWebCrawler
from google import genai

load_dotenv()

class DeepSearchTool():
    def __init__(self, query):
        self.query = query
        self.engine = "google"
        self.num_links = 10
        self.kb_id = str(uuid.uuid4())  # Generate unique ID with UUID
        self.knowledge_file = f"knowledge_{self.kb_id}.md"
        self.links = []
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def search_different_websites_serpapi(self) -> List[str]:
        """
        Searches a query using SerpApi, returns the top links.

        Args:
            query: The search query.
            num_links: The number of links to return.
            engine: Search Engine to be used, "brave" by default.

        Returns:
            A list of URLs.
        """
        params = {
            "q": self.query,
            "api_key": os.getenv("SERPAPI_API_KEY"),  # Get API key from environment variable
            "engine": self.engine,  # default to Brave, but could be others
        }

        if not params["api_key"]:
            raise ValueError("SERPAPI_API_KEY environment variable not set.")

        search = serpapi.search(params)

        results = search.get("organic_results", [])
        print(f"[SERVER]: Found {len(results)} results. ")

        # Extract the links, making sure to handle cases where 'link' might be missing
        links: List[str] = []
        for result in results:
            if "link" in result:  # Safely check for the 'link' key
                links.append(result["link"])
        
        self.links = links[:self.num_links]  # Store links in instance variable
        return self.links

    async def crawl_and_create_knowledge_file(self):
        """
        Crawls each website from search results using AsyncWebCrawler and 
        creates a single consolidated knowledge file with source headings.
        
        Returns:
            str: Path to the created knowledge file
        """
        if not self.links:
            # If links haven't been fetched yet, fetch them
            self.search_different_websites_serpapi()
            
        if not self.links:
            print(f"[SERVER]: No URLs found to crawl.")
            return None
        
        print(f"[SERVER]: Starting crawl of {len(self.links)} websites into knowledge file: {self.knowledge_file}")
        
        # Create or truncate the knowledge file with a title
        with open(self.knowledge_file, "w") as f:
            f.write(f"# Knowledge Base for: {self.query}\n\n")
            f.write(f"Generated on: {asyncio.get_running_loop().time()}\n\n")
            f.write("---\n\n")
        
        async def crawl():
            async with AsyncWebCrawler() as crawler:
                for i, link in enumerate(self.links):
                    try:
                        print(f"[SERVER]: Crawling {i+1}/{len(self.links)}: {link}")
                        result = await crawler.arun(url=link)
                        
                        # Append this source's content to the knowledge file with a heading
                        with open(self.knowledge_file, "a") as f:
                            f.write(f"## Source {i+1}: {link}\n\n")
                            f.write(result.markdown)
                            f.write("\n\n---\n\n")  # Add separator between sources
                            
                        print(f"[SERVER]: Successfully added {link} to knowledge file")
                    except Exception as e:
                        print(f"[SERVER]: Error crawling {link}: {str(e)}")
                        # Document the error in the knowledge file
                        with open(self.knowledge_file, "a") as f:
                            f.write(f"## Source {i+1}: {link}\n\n")
                            f.write(f"*Error crawling this source: {str(e)}*\n\n")
                            f.write("---\n\n")
        
        await crawl()
        print(f"[SERVER]: Knowledge file created at: {os.path.abspath(self.knowledge_file)}")
        return os.path.abspath(self.knowledge_file)
    
    def crawl_each_website_and_prepare_knowledge_base(self):
        """
        Synchronous wrapper for the async crawl_and_create_knowledge_file method.
        
        Returns:
            str: Path to the created knowledge file
        """
        return asyncio.run(self.crawl_and_create_knowledge_file())
    
    def get_kb_path(self):
        """Returns the path to the knowledge file"""
        return os.path.abspath(self.knowledge_file)
    
    def clean_up(self):
        """Removes the knowledge file"""
        if os.path.exists(self.knowledge_file):
            os.remove(self.knowledge_file)
            print(f"[SERVER]: Cleaned up knowledge file: {self.knowledge_file}")


    def generate_summarisation(self, path):
        myfile = self.client.files.upload(file=path)
        system_prompt = """

You are a research assistant tasked with synthesizing information from a diverse knowledge base into a concise and well-organized research report in Markdown format. The knowledge base may contain information about an individual, a project, an organization, or a concept. Your goal is to create a clear and informative summary, drawing out the most important and relevant details.

**INPUT:** A multi-source knowledge base consisting of:

*   Markdown files (content provided directly)
*   Web links (HTML content, which will be provided to you as pre-processed text)
*   Other text-based sources (e.g., social media posts, documents – content provided directly)
"""

        user_query = "Generate a comprehensive research report in Markdown format based on the provided knowledge base."
        result = self.client.models.generate_content(
            model="gemini-2.0-pro-exp-02-05",
            contents=[myfile, system_prompt, user_query],
        )

        # save response .text

        with open("response.md", "w") as f:
            f.write(result.text)

        return result.text

# Example usage
if __name__ == "__main__":
    deepSearch = DeepSearchTool("Ashish Kumar Verma IIT Delhi")
    # # First search and get URLs
    # urls = deepSearch.search_different_websites_serpapi()
    # print(f"[SERVER]: Found URLs: {urls}")

    # Then crawl and create knowledge file

    # kb_path = deepSearch.crawl_each_website_and_prepare_knowledge_base()
    # print(f"[SERVER]: Knowledge file created at: {kb_path}")

    print(deepSearch.generate_summarisation("./knowledge_8d2b33d5-5832-4954-bd82-1e4a81090512.md"))

    
    # Optional: clean up after you're done
    # deepSearch.clean_up()