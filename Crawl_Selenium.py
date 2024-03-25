from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re
import os
from bs4 import BeautifulSoup
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin

def sanitize_filename(url):
    sanitized = re.sub(r'[?<>:"/\\|*]', '_', url)
    return sanitized

HTTP_URL_PATTERN = r'^http[s]?://.+'
domain = "www.example.com" #domain
path_keyword = "/path" #path

class HyperlinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hyperlinks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.hyperlinks.append(attrs["href"])

def get_hyperlinks(url, driver):
    try:
        driver.get(url)
        html = driver.page_source
    except Exception as e:
        print(e)
        return []

    parser = HyperlinkParser()
    parser.feed(html)
    return parser.hyperlinks

def get_domain_hyperlinks(url, driver):
    clean_links = []
    for link in set(get_hyperlinks(url, driver)):
        absolute_link = urljoin(url, link)
        if urlparse(absolute_link).netloc == domain and path_keyword in absolute_link:
            clean_links.append(absolute_link)
    return list(set(clean_links))

def crawl(url):
    # Initialize Selenium WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    queue = deque([url])
    seen = set([url])

    while queue:
        current_url = queue.popleft()
        print("Crawling:", current_url)

        filename = sanitize_filename(current_url)
        file_path = f'text_selenium/{domain}/{filename}.txt'
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            driver.get(current_url)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            text = soup.get_text()
            with open(file_path, "w", encoding="UTF-8") as f:
                f.write(text)
        except Exception as e:
            print(f"Failed to process {current_url}: {e}")
            continue

        for link in get_domain_hyperlinks(current_url, driver):
            if link not in seen:
                queue.append(link)
                seen.add(link)

    driver.quit()

initial_url = "https://www.example.com/path"
crawl(initial_url)
