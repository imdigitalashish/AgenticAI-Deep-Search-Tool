import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

def scrape_duckduckgo_content(query, num_pages):
    links = []
    
    # Configure Selenium Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Initialize the Selenium WebDriver
    with webdriver.Chrome(options=chrome_options) as driver:
        for page in range(num_pages):
            start = page * 30  # DuckDuckGo uses increments of 30 for pagination
            search_url = f"https://duckduckgo.com/html/?q={query}&s={start}"
            
            print(f"Fetching: {search_url}")
            
            try:
                # Fetch the page using Selenium
                driver.get(search_url)
                
                # Wait for the page to load (you can adjust this time if needed)
                time.sleep(5)
                
                # Parse the page source with BeautifulSoup
                soup = BeautifulSoup(driver.page_source, "html.parser")
                
                # Extract search results
                for result in soup.find_all("div", class_="result__body"):
                    title_tag = result.find("a", class_="result__a")
                    link_tag = result.find("a", href=True)
                    
                    if title_tag and link_tag:
                        link = link_tag["href"]
                        # DuckDuckGo uses redirect links, so we extract the actual URL
                        actual_link = link.split("uddg=")[-1].split("&")[0]
                        links.append(actual_link)
                        print(f"Found link: {actual_link}")
            
            except WebDriverException as e:
                print(f"WebDriverException occurred: {e}")
            except Exception as e:
                print(f"Error occurred while scraping DuckDuckGo search results: {e}")
        
        return links

