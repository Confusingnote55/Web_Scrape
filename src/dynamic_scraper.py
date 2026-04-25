import os
import sys
import json
import time
import logging
import shutil
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from tqdm import tqdm

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('selenium').setLevel(logging.WARNING)

def get_page_source_with_selenium(driver, url, wait_for_selector):
    """Navigates to a URL and waits for a specific element to appear."""
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
        )
        return driver.page_source
    except Exception as e:
        logging.error(f"Selenium failed to load {url} or find element '{wait_for_selector}': {e}")
        return ""

def get_all_links_with_pagination(index_url, base_url, link_selector, next_page_selector):
    """
    Scrapes an index page for all links, automatically handling pagination by clicking a 'next' button.
    """
    options = Options()
    options.add_argument('--headless')
    service = Service()
    driver = webdriver.Firefox(service=service, options=options)
    
    all_links = []
    current_url = index_url

    try:
        driver.get(current_url)
        # Handle initial cookie banner on the first page
        try:
            cookie_button_xpath = "//button[contains(., 'Accept all') or contains(., 'Accept')]"
            cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.XPATH, cookie_button_xpath)))
            cookie_button.click()
            logging.info("Cookie consent button clicked.")
            time.sleep(2)
        except Exception:
            logging.info("No cookie consent banner found.")

        page_num = 1
        while True:
            logging.info(f"Scraping links from page: {current_url}")
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, link_selector)))
            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            link_elements = soup.select(link_selector)
            if not link_elements:
                logging.warning(f"No links found on page {page_num}.")
                break
            
            for link_tag in link_elements:
                href = link_tag.get('href')
                if href and "http" in href:
                    all_links.append(href)

            try:
                # Find the 'Next Page' button and click it
                next_button = driver.find_element(By.CSS_SELECTOR, next_page_selector)
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(3) # Wait for the new page to load
                current_url = driver.current_url
                page_num += 1
            except Exception:
                logging.info("No more 'Next Page' buttons found. Concluding link gathering.")
                break # Exit loop if no 'next' button is found
    
    except Exception as e:
        logging.error(f"An error occurred during link gathering: {e}")
    finally:
        driver.quit()

    return sorted(list(set(all_links)))


def scrape_page(url, title_selector, content_selector):
    """Scrapes a single content page and converts its content to Markdown."""
    # This function can reuse a simplified selenium loader without pagination logic
    options = Options()
    options.add_argument('--headless')
    service = Service()
    driver = webdriver.Firefox(service=service, options=options)
    html_content = ""
    try:
        html_content = get_page_source_with_selenium(driver, url, content_selector)
    finally:
        driver.quit()

    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'lxml')
    markdown_lines = []
    
    title_tag = soup.select_one(title_selector)
    if title_tag:
        markdown_lines.append(f"# {title_tag.get_text(strip=True)}\n")

    content_container = soup.select_one(content_selector)
    if content_container:
        for element in content_container.find_all(['h3', 'p', 'ul', 'ol']):
            if element.name == 'h3':
                markdown_lines.append(f"### {element.get_text(strip=True)}\n")
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text:
                    markdown_lines.append(f"{text}\n")
            elif element.name in ['ul', 'ol']:
                for li in element.find_all('li', recursive=False):
                    text = li.get_text(strip=True)
                    if text:
                        markdown_lines.append(f"* {text}")
                markdown_lines.append("")

    return "\n".join(markdown_lines)


def main():
    """Sets up the CLI arguments and orchestrates the entire scraping process."""
    parser = argparse.ArgumentParser(description="A dynamic web scraper with pagination handling.")
    
    parser.add_argument('project_name', help="A name for your project.")
    parser.add_argument('--index_url', required=True, help="The starting URL of the index page.")
    parser.add_argument('--base_url', required=True, help="The base URL for constructing full links.")
    parser.add_argument('--link_selector', required=True, help="The CSS selector for the article links.")
    parser.add_argument('--next_page_selector', required=True, help="The CSS selector for the 'Next Page' button.")
    parser.add_argument('--title_selector', required=True, help="The CSS selector for the article title.")
    parser.add_argument('--content_selector', required=True, help="The CSS selector for the article content container.")
    parser.add_argument('--delay', type=int, default=3, help="Delay between scraping each article.")

    args = parser.parse_args()
    
    urls_file_path = f"data/{args.project_name}_urls.json"
    all_links = get_all_links_with_pagination(args.index_url, args.base_url, args.link_selector, args.next_page_selector)
    
    if not all_links:
        logging.error("No links were found. Exiting.")
        sys.exit(1)
        
    with open(urls_file_path, 'w') as f:
        json.dump(all_links, f, indent=2)
    logging.info(f"Found {len(all_links)} links across all pages. Saved to {urls_file_path}.")
    
    try:
        input("\nPress Enter to continue with scraping content...")
    except KeyboardInterrupt:
        logging.info("\nExiting.")
        sys.exit(0)

    output_dir = f"data/scraped_{args.project_name}"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    logging.info(f"Starting content scrape for {len(all_links)} URLs...")
    for url in tqdm(all_links, desc=f"Scraping {args.project_name}"):
        topic_id = url.strip('/').split('/')[-1] if url.strip('/') else 'index'
        markdown_content = scrape_page(url, args.title_selector, args.content_selector)
        
        if not markdown_content.strip():
             tqdm.write(f"WARNING: No content found for {topic_id}.")
        
        md_path = f"{output_dir}/{topic_id}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        time.sleep(args.delay)
    
    logging.info("Scraping complete.")

if __name__ == "__main__":
    main()
