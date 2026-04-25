from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define constants
SITEMAP_URL = "https://geekymedics.com/sitemap_index.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def take_screenshot(url, attempt):
    """Take a screenshot of the given URL and save it."""
    try:
        # Set up Firefox options
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument("--headless")  # Run in headless mode
        firefox_options.set_preference("general.useragent.override", HEADERS["User-Agent"])

        # Initialize WebDriver
        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=firefox_options)

        # Load the URL and wait for content
        logging.info(f"Attempt {attempt + 1} - Loading {url}...")
        driver.get(url)
        time.sleep(5)  # Wait for page to load, including potential JavaScript

        # Take screenshot
        screenshot_path = f"sitemap_screenshot_attempt{attempt}.png"
        driver.save_screenshot(screenshot_path)
        logging.info(f"Screenshot saved as {screenshot_path}")

        # Get page source for reference
        page_source = driver.page_source
        with open(f"sitemap_source_attempt{attempt}.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        logging.info(f"Page source saved as sitemap_source_attempt{attempt}.html")

        driver.quit()
        return page_source
    except Exception as e:
        logging.error(f"Attempt {attempt + 1} failed: {e}")
        if 'driver' in locals():
            driver.quit()
        return None

def main():
    """Main function to run the screenshot debug process."""
    logging.info("Starting screenshot debug process...")
    for attempt in range(3):
        page_source = take_screenshot(SITEMAP_URL, attempt)
        if page_source:
            break
        time.sleep(2 ** attempt)  # Exponential backoff
    if not page_source:
        logging.error("Failed to capture screenshot after 3 attempts.")

if __name__ == "__main__":
    main()
