from pydantic_ai import Agent, RunContext
import groq
from dotenv import load_dotenv
import datetime
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

load_dotenv()

def google_search(query: str, num_results=5):
    """
    Scrapes Google search results.

    Args:
        query: The search query.
        num_results: The number of results to return.

    Returns:
        A list of dictionaries, each containing the title, link, and snippet of a search result.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
    }
    url = f"https://www.google.com/search?q={query}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    results = []

    # Find the search result containers. The CSS selector might need adjustment
    # if Google changes its page structure.
    for g in soup.find_all('div', class_='g'):
        # Find title
        title_tag = g.find('h3')

        # Find link
        link_tag = g.find('a')

        # Find snippet
        snippet_tag = g.find('span', class_='st')  # This class might vary

        if title_tag and link_tag and snippet_tag:
            title = title_tag.text
            link = link_tag['href']
            snippet = snippet_tag.text

            results.append({
                'title': title,
                'link': link,
                'snippet': snippet
            })
    return results[:num_results]

async def fetch_creator_username(ctx: RunContext):
    return "My creator is imdigitalashish"

async def search_and_respond(ctx: RunContext, query: str):
    """
    Performs a Google search and returns a summary of the results.
    """
    search_results = google_search(query)
    if not search_results:
        return "Could not find information on the web."

    # Format the search results into a string response
    summary = ""
    for result in search_results:
        summary += f"{result['title']}\n{result['snippet']}\n{result['link']}\n\n"

    return f"Here's what I found on the web about {query}:\n\n{summary}"

class ProgrammingDefinition(BaseModel):
    definition: str

agent = Agent(
    model="groq:llama3-70b-8192",
    tools=[search_and_respond],
    result_type=ProgrammingDefinition
)

result = agent.run_sync("Who's your creator? respond with coolness")
print(result.data.definition)

result = agent.run_sync("Patches over token")
print(result.data.definition)