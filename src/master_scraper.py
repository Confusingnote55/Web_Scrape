import os
import logging
import argparse
import json
import time
import hashlib
from urllib.parse import urljoin, urlparse

# Standard library imports
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Third-party imports
from usp.tree import sitemap_tree_for_homepage
from usp.web_client.requests_client import RequestsWebClient
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.common.exceptions import TimeoutException
from PIL import Image
import io

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


def find_main_content(soup):
    """
    Heuristically finds the main content block of an article.
    """
    selectors = [
        '#content', '.post-content', '.entry-content', 'article', 'main',
        '.article-content', '.article-body', '#main', '.post'
    ]
    for selector in selectors:
        main_content = soup.select_one(selector)
        if main_content and len(main_content.get_text(strip=True)) > 200:
            return main_content
    return None


def get_page_source_with_selenium(driver, url):
    """Uses Selenium to get the full page source after JS rendering."""
    try:
        driver.get(url)
        time.sleep(3)
        return driver.page_source
    except Exception as e:
        tqdm.write(f" Selenium error for URL {url}: {e}")
        return None


def get_all_article_urls(homepage_url, user_agent, scope_url=None, exclude_keywords=None):
    """
    STAGE 1: Scrapes the sitemap and filters URLs based on scope and exclusion keywords.
    """
    logging.info(f"--- STAGE 1: Starting Sitemap Scrape for {homepage_url} ---")
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': user_agent})
        web_client = RequestsWebClient(session=session)
        tree = sitemap_tree_for_homepage(homepage_url=homepage_url, web_client=web_client)
        all_urls = [page.url for page in tree.all_pages()]
        logging.info(f"Sitemap scrape complete. Found {len(all_urls)} total URLs.")

        # --- NEW: Filter URLs based on exclusion keywords ---
        if exclude_keywords:
            keywords_to_exclude = [kw.strip() for kw in exclude_keywords.split(',')]
            original_count = len(all_urls)
            all_urls = [url for url in all_urls if not any(keyword in url for keyword in keywords_to_exclude)]
            logging.info(f"Excluded {original_count - len(all_urls)} URLs based on keywords.")

        # Filter URLs based on the scope
        if scope_url:
            original_count = len(all_urls)
            all_urls = [url for url in all_urls if url.startswith(scope_url)]
            logging.info(f"Filtered to {len(all_urls)} URLs within the scope: {scope_url}")
            
        return all_urls

    except Exception as e:
        logging.error(f"Sitemap scraping failed: {e}", exc_info=True)
        return []


def download_images(article_div, page_url, output_dir):
    """
    Finds, downloads, and converts images, handling WebP format.
    """
    if not article_div: return []
    images = article_div.find_all('img')
    if not images: return []
    
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    session = requests.Session()
    image_metadata_list = []

    for i, img in enumerate(images):
        src = img.get('src')
        if not src or not src.startswith('http'): continue
        
        image_url = urljoin(page_url, src)
        try:
            session.headers.update({'Referer': page_url})
            img_response = session.get(image_url, stream=True, timeout=10)
            img_response.raise_for_status()

            content_type = img_response.headers.get('content-type')
            if 'webp' in content_type:
                image_bytes = io.BytesIO(img_response.content)
                webp_image = Image.open(image_bytes).convert("RGBA")
                url_hash = hashlib.md5(page_url.encode()).hexdigest()
                image_filename = f"{url_hash}_image-{i+1}.png" 
                image_filepath = os.path.join(images_dir, image_filename)
                webp_image.save(image_filepath, 'PNG')
            else:
                url_hash = hashlib.md5(page_url.encode()).hexdigest()
                image_filename = f"{url_hash}_image-{i+1}.jpg"
                image_filepath = os.path.join(images_dir, image_filename)
                with open(image_filepath, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192): f.write(chunk)
            
            image_metadata = {
                "image_file": image_filepath, "alt_text": img.get('alt', ''),
                "caption": img.find_next_sibling('figcaption').get_text(strip=True) if img.find_next_sibling('figcaption') else ''
            }
            image_metadata_list.append(image_metadata)
        except (requests.exceptions.RequestException, IOError):
            pass
        except Exception as e:
            tqdm.write(f" An error occurred processing image {image_url}: {e}")
    return image_metadata_list


def process_article(url, output_dir, user_agent, selenium_driver=None):
    """
    Processes a single article, trying requests first, then falling back to Selenium.
    """
    article_div = None
    soup = None

    try:
        response = requests.get(url, headers={'User-Agent': user_agent, 'Referer': url}, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        article_div = find_main_content(soup)
        
        if not article_div and selenium_driver:
             tqdm.write(f" Requests failed for {url}, falling back to Selenium.")
             raise ValueError("Triggering Selenium fallback")
             
    except (requests.exceptions.RequestException, ValueError):
        if not selenium_driver: return
        
        html_source = get_page_source_with_selenium(selenium_driver, url)
        if not html_source: return
        soup = BeautifulSoup(html_source, 'html.parser')
        article_div = find_main_content(soup)

    if not article_div:
        tqdm.write(f" Could not find main content for URL: {url}")
        return

    image_metadata = download_images(article_div, url, output_dir)
    title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "No Title Found"
    
    for element in article_div.find_all(['form', 'button', 'script', 'nav', 'footer', 'header']):
        element.decompose()

    article_data = {
        "url": url, "title": title, "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "clean_text": article_div.get_text(separator='\n', strip=True),
        "html_content": str(article_div), "images": image_metadata
    }
    
    url_hash = hashlib.md5(url.encode()).hexdigest()
    json_filepath = os.path.join(output_dir, 'json_articles', f"{url_hash}.json")
    
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(article_data, f, indent=4)


def download_articles(urls, output_dir, user_agent):
    """
    STAGE 2: Downloads all articles using the hybrid requests/Selenium approach.
    """
    logging.info(f"--- STAGE 2: Starting Hybrid Article Download ---")
    json_output_dir = os.path.join(output_dir, 'json_articles')
    os.makedirs(json_output_dir, exist_ok=True)
    
    selenium_driver = None
    try:
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        options.set_preference("general.useragent.override", user_agent)
        selenium_driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
    except Exception as e:
        logging.error(f"Could not initialize Selenium. Proceeding with requests only. Error: {e}")

    for url in tqdm(urls, desc="Scraping Articles", unit="article", ncols=100):
        path_segments = urlparse(url).path.strip('/').split('/')
        if len(path_segments) < 2 and path_segments[0] != '':
            tqdm.write(f" Skipping potential index page: {url}")
            continue
        process_article(url, output_dir, user_agent, selenium_driver)
    
    if selenium_driver:
        selenium_driver.quit()


def main():
    """ Main function to parse arguments and run the scraper. """
    parser = argparse.ArgumentParser(
        description="A universal, hybrid web scraper to download articles into a structured output directory.",
        epilog="Example: python %(prog)s https://example.com/ -o data --scope https://example.com/blog/ --exclude about,contact"
    )
    parser.add_argument("homepage_url", help="The homepage URL of the target website.")
    parser.add_argument("-o", "--output-dir", default="scraped_output", help="The directory for scraped data.")
    parser.add_argument("-u", "--user-agent", default='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36', help="User-Agent for requests.")
    parser.add_argument("--scope", help="Optional: Only scrape URLs starting with this path (e.g., https://cks.nice.org.uk/topics/).")
    # --- NEW ARGUMENT ---
    parser.add_argument("--exclude", help="Optional: A comma-separated list of keywords. URLs containing any of these keywords will be excluded (e.g., 'about,contact').")
    
    args = parser.parse_args()

    urls_to_process = get_all_article_urls(args.homepage_url, args.user_agent, args.scope, args.exclude)
    
    if urls_to_process:
        download_articles(urls_to_process, args.output_dir, args.user_agent)
        logging.info("--- All tasks complete. ---")
    else:
        logging.error("--- Script finished with errors: Could not retrieve any URLs. ---")

if __name__ == '__main__':
    main()
