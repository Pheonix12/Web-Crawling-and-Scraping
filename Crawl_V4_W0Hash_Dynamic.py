import asyncio
import re
import random
from collections import deque
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
from pathlib import Path
import json
import signal
import sys

# Constants
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
MAX_PATH_LENGTH = 250

# Function to manage unique filenames
def get_unique_filename(base_path):
    counter = 1
    while base_path.exists():
        base_path = base_path.with_name(f"{base_path.stem}_{counter}{base_path.suffix}")
        counter += 1
    return base_path

# Function to sanitize and generate a unique filename for saved files
def sanitize_filename(url):
    trimmed_url = url.replace(f'https://{DOMAIN}{PATH_KEYWORD}', '').lstrip('/')
    sanitized_filename = re.sub(r'[?<>:"/\\|*]', '_', trimmed_url)
    sanitized_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '', sanitized_filename)
    file_path = BASE_DIRECTORY / (sanitized_filename + '.txt')
    while len(str(file_path)) > MAX_PATH_LENGTH:
        sanitized_filename = sanitized_filename[:-1]
        file_path = BASE_DIRECTORY / (sanitized_filename + '.txt')
    return get_unique_filename(file_path)

# Extract and filter hyperlinks with BeautifulSoup, including a duplicate check
def extract_hyperlinks(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    clean_links = []
    for link in links:
        if link:
            absolute_link = urljoin(base_url, link)
            if urlparse(absolute_link).netloc == DOMAIN and PATH_KEYWORD in absolute_link:
                # Check if the absolute link is neither in seen nor already in the queue
                if absolute_link not in seen and absolute_link not in queue:
                    clean_links.append(absolute_link)
    return list(set(clean_links))

async def click_read_more_buttons(page):
    read_more_buttons_selector = '.read-more'
    try:
        read_more_buttons = await page.query_selector_all(read_more_buttons_selector)
        for button in read_more_buttons:
            await button.click()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error clicking 'Read More' buttons: {e}")

# Adjusted save_state function to filter the queue before saving
def save_state():
    with open(QUEUE_FILE, 'w') as qf, open(SEEN_FILE, 'w') as sf:
        # Filter the queue to remove any URLs already in seen or duplicates before saving
        filtered_queue = [url for url in queue if url not in seen]
        json.dump(list(filtered_queue), qf)
        json.dump(list(seen), sf)

# Adjusting load_state to ensure no duplicates are added back into the queue
def load_state():
    if QUEUE_FILE.exists() and SEEN_FILE.exists():
        with open(QUEUE_FILE, 'r') as qf, open(SEEN_FILE, 'r') as sf:
            loaded_queue = json.load(qf)
            loaded_seen = set(json.load(sf))
            # Update seen with loaded seen
            seen.update(loaded_seen)
            # Extend the queue only with URLs that are not in seen
            for url in loaded_queue:
                if url not in seen:
                    queue.append(url)

async def crawl(start_url, playwright, semaphore):
    async with semaphore:
        if not queue or not seen:
            queue.append(start_url)

        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        try:
            while queue:
                current_url = queue.popleft()
                print(f"Crawling: {current_url}")
                retry_count = 0
                while retry_count < 3:
                    try:
                        await page.goto(current_url, wait_until="networkidle", timeout=60000)
                        await click_read_more_buttons(page)
                        await asyncio.sleep(random.uniform(1, 3))

                        html = await page.content()
                        file_path = sanitize_filename(current_url)
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(BeautifulSoup(html, "html.parser").get_text())

                        seen.add(current_url)
                        save_state()

                        for link in extract_hyperlinks(html, current_url):
                            if link not in seen:
                                queue.append(link)
                        break
                    except TimeoutError:
                        retry_count += 1
                    except Exception as e:
                        print(f"Error processing {current_url}: {e}")
                        break
        finally:
            await page.close()
            await context.close()
            await browser.close()

async def parallel_crawl(start_urls, concurrency=4):
    load_state()  # Load the initial state
    async with async_playwright() as playwright:
        semaphore = asyncio.Semaphore(concurrency)
        tasks = []
        for url in start_urls:
            task = asyncio.create_task(crawl(url, playwright, semaphore))
            tasks.append(task)
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    def graceful_exit():
        save_state()
        sys.exit(0)

    signal.signal(signal.SIGINT, lambda sig, frame: asyncio.run(graceful_exit()))
    signal.signal(signal.SIGTERM, lambda sig, frame: asyncio.run(graceful_exit()))

    initial_url = input("Please enter the initial URL to start crawling from: ")

    # Parse the initial URL to get the domain and path keyword
    parsed_url = urlparse(initial_url)
    DOMAIN = parsed_url.netloc
    PATH_KEYWORD = parsed_url.path

    # Set base directory for saving files
    BASE_DIRECTORY = Path('text_2').joinpath(DOMAIN.replace('.', '_'))
    BASE_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Set state directories
    STATE_DIR = Path('text_2/crawl_state')
    STATE_DIR.mkdir(exist_ok=True)
    QUEUE_FILE = STATE_DIR / 'queue.json'
    SEEN_FILE = STATE_DIR / 'seen.json'

    # Initialize queue and seen at a global scope
    queue = deque()
    seen = set()

    asyncio.run(parallel_crawl([initial_url], concurrency=4))
