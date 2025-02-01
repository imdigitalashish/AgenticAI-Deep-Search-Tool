from pydantic_ai import Agent, RunContext
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from typing import List

import time

import httpx
from bs4 import BeautifulSoup
import time
from pydantic_ai import Agent, RunContext
class SearchResult(BaseModel):
    title: str
    snippet: str
    link: str
    content: str = Field(default="")

class AggregatedResults(BaseModel):
    results: List[SearchResult]
def scrape_page_content(client: httpx.Client, url: str, headers: dict) -> str:
    """Scrape and extract text content from a given URL."""
    try:
        print(f"Scraping content from: {url}")
        response = client.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract text from paragraphs
        paragraphs = soup.find_all("p")
        content = " ".join([para.get_text() for para in paragraphs])

        # Optional: Further processing to clean or summarize content
        return content
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred while fetching {url}: {e}")
        return "Failed to retrieve content."
    except Exception as e:
        print(f"An error occurred while scraping {url}: {e}")
        return "Error during content scraping."

def scrape_google(ctx: RunContext, query: str, num_pages: int = 5) -> AggregatedResults:
    """Scrape Google search results and scrape content from each linked page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    search_url = "https://www.google.com/search"
    aggregated_results = AggregatedResults(results=[])

    with httpx.Client(timeout=30) as client:
        for page in range(num_pages):
            start = page * 10  # Google shows 10 results per page
            params = {"q": query, "hl": "en", "start": start}
            print(f"Fetching: {search_url}?q={params['q']}&start={start}")
            
            try:
                response = client.get(search_url, headers=headers, params=params)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                # Extract search result titles and links
                for g in soup.find_all("div", class_="tF2Cxc"):
                    title_tag = g.find("h3")
                    link_tag = g.find("a", href=True)
                    snippet_tag = g.find("span", class_="aCOpRe")
                    
                    if title_tag and link_tag:
                        title = title_tag.text
                        link = link_tag["href"]
                        snippet = snippet_tag.text if snippet_tag else ""
                        
                        # Initialize SearchResult without content
                        search_result = SearchResult(
                            title=title,
                            snippet=snippet,
                            link=link
                        )
                        
                        # Scrape content from the linked page
                        search_result.content = scrape_page_content(client, link, headers)
                        
                        # Append to aggregated results
                        aggregated_results.results.append(search_result)
                        
                        # Optional: Limit to 50 results
                        if len(aggregated_results.results) >= 50:
                            break
            except httpx.HTTPStatusError as e:
                print(f"HTTP error occurred while fetching search results: {e}")
                break  # Exit the loop if a page fails to load
            except Exception as e:
                print(f"An error occurred while fetching search results: {e}")
                break  # Exit the loop on any other exception

            # Optional: Delay between page fetches to avoid rate limiting
            time.sleep(2)

    return aggregated_results if aggregated_results.results else AggregatedResults(results=[])

class ProgrammingDefinition(BaseModel):
    definition: str


# Update tools to include the scrape_google tool

a = scrape_google(RunContext, "As")
print(a)
# agent = Agent(
#     model="groq:llama3-70b-8192",
#     tools=[scrape_google],
#     result_type=ProgrammingDefinition
# )

# Query using the Google scraping feature
# result = agent.run_sync("Patches over tokens")
# print(result.data.definition)