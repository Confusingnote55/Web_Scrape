import os
import json
import logging
import argparse
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm

# Suppress noisy Selenium logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('selenium').setLevel(logging.WARNING)

def get_sub_index_links(start_url, wait_for_selector, link_selector):
    """
    Scrapes a top-level index page for sub-index URLs with robust pop-up handling.
    """
    logging.info(f"Starting to scrape sub-index links from: {start_url}")
    
    options = Options()
    options.add_argument('--headless')
    service = Service()
    driver = webdriver.Firefox(service=service, options=options)
    
    sub_index_links = []
    try:
        driver.get(start_url)
        time.sleep(3) # A brief initial wait for things to start loading

        # --- OPTIMIZED: More specific and robust cookie handling ---
        try:
            # Using the specific ID of the button is more reliable
            cookie_button_selector = "button#cky-btn-accept"
            cookie_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, cookie_button_selector))
            )
            cookie_button.click()
            logging.info("Clicked main cookie consent button.")
            time.sleep(2) # Allow time for the banner to disappear
        except Exception:
            logging.info("No cookie consent banner found or it was not clickable within the time limit.")
            
        # --- OPTIMIZED: Using a more reliable wait condition ---
        # Waits for the element to be in the DOM, not necessarily visible.
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
        )
        logging.info("Main content landmark is now present in the DOM.")
        
        # Find all the link elements
        link_elements = driver.find_elements(By.CSS_SELECTOR, link_selector)
        
        for link in tqdm(link_elements, desc="Extracting links"):
            href = link.get_attribute('href')
            if href:
                sub_index_links.append(href)
        
    except Exception as e:
        logging.error(f"An error occurred during scraping: {e}")
    finally:
        driver.quit()

    return sorted(list(set(sub_index_links)))

def main():
    """Sets up CLI arguments and runs the sub-index scraper."""
    parser = argparse.ArgumentParser(description="A dynamic CLI tool to find and save sub-index URLs from a main index page.")
    
    parser.add_argument('project_name', help="A name for your project (e.g., 'geekymedics_mla').")
    parser.add_argument('--start_url', required=True, help="The URL of the top-level index page.")
    parser.add_argument('--wait_selector', required=True, help="A stable CSS selector on the page to wait for before scraping.")
    parser.add_argument('--link_selector', required=True, help="The CSS selector to find all the sub-index links.")
    
    args = parser.parse_args()
    
    output_file = f"data/{args.project_name}_sub_urls.json"
    
    unique_links = get_sub_index_links(args.start_url, args.wait_selector, args.link_selector)
    
    if unique_links:
        os.makedirs('data', exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(unique_links, f, indent=2)
        logging.info(f"Found {len(unique_links)} unique sub-index links. Saved to {output_file}")
    else:
        logging.warning("No sub-index links were found.")

if __name__ == "__main__":
    main()
