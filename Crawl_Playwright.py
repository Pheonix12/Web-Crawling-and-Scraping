import asyncio
import os
import re
import random
from collections import deque
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Constants
DOMAIN = "www.example.com" #domain
PATH_KEYWORD = "/path" #path
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"


# Utility function to sanitize filenames
def sanitize_filename(url):
    return re.sub(r'[?<>:"/\\|*]', '_', url)


# Extract and filter hyperlinks with BeautifulSoup
def extract_hyperlinks(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    clean_links = []
    for link in links:
        if link:
            absolute_link = urljoin(base_url, link)
            if urlparse(absolute_link).netloc == DOMAIN and PATH_KEYWORD in absolute_link:
                clean_links.append(absolute_link)
    return list(set(clean_links))


# Main crawler function with enhancements for 403 errors
async def crawl(start_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        queue = deque([start_url])
        seen = set([start_url])

        while queue:
            current_url = queue.popleft()
            print("Crawling:", current_url)

            try:
                await page.goto(current_url, wait_until="networkidle")
                await page.wait_for_selector('body', state="attached")
                await asyncio.sleep(random.uniform(1, 4))  # Random delay to mimic human behavior

                html = await page.content()
                file_path = f'text_playwright/{DOMAIN}/{sanitize_filename(current_url)}.txt'
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(BeautifulSoup(html, "html.parser").get_text())

                for link in extract_hyperlinks(html, current_url):
                    if link not in seen:
                        queue.append(link)
                        seen.add(link)

            except Exception as e:
                print(f"Error processing {current_url}: {e}")

        await browser.close()


# Start crawling
initial_url = "https://www.example.com/path"  # Change to your initial URL
asyncio.run(crawl(initial_url))
