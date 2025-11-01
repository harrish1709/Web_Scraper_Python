from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, random, re, os, traceback
from datetime import datetime
from scrapers.utils import polite_delay, save_to_excel

# ✅ Initialize reusable driver
def init_amazon_driver():
    chromium_path = "/usr/bin/chromium-browser"
    chromedriver_path = "/usr/bin/chromedriver"
    if not os.path.exists(chromium_path):
        chromium_path = "/usr/bin/chromium"
    if not os.path.exists(chromedriver_path):
        chromedriver_path = "/usr/lib/chromium-browser/chromedriver"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.7390.122 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.7390.122 Safari/537.36",
    ])
    options.add_argument(f"--user-agent={ua}")
    options.binary_location = chromium_path

    driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def quit_amazon_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass


def scrape_amazon(query, driver=None):
    """Scrape Amazon using an existing driver (or create a temporary one)."""
    close_after = False
    if driver is None:
        driver = init_amazon_driver()
        close_after = True

    try:
        polite_delay()
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
        )

        html = driver.page_source
        if "To discuss automated access" in html or "Enter the characters you see below" in html:
            return {"error": "Blocked by Amazon (CAPTCHA or rate-limit)."}

        soup = BeautifulSoup(html, "html.parser")
        product_cards = soup.select("div[data-component-type='s-search-result']")

        scraped_data = []

        for card in product_cards:
            url_tag = card.select_one("a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal") \
                       or card.select_one("a.a-link-normal.s-no-outline")
            product_url = "https://www.amazon.in" + url_tag["href"] if url_tag else "N/A"

            name_tag = card.select_one("h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal") \
                       or card.select_one("h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal")
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            price_tag = card.select_one("span.a-price > span.a-offscreen") or card.select_one("span.a-color-price")
            raw_price = price_tag.text.strip() if price_tag else "NA"

            price_nums = [p for p in re.findall(r"[\d,]+(?:\.\d+)?", raw_price) if p.strip()]
            if not price_nums:
                continue

            try:
                price_value = int(float(price_nums[0].replace(",", "")))
            except ValueError:
                continue

            currency_match = re.search(r"([$€£₹]|Rs)", raw_price)
            currency = currency_match.group(0) if currency_match else "NA"

            rating_tag = card.select_one("span.a-icon-alt")
            rating = rating_tag.get_text(strip=True).replace("out of 5 stars", "").strip() if rating_tag else "N/A"

            scraped_data.append({
                "SOURCE URL": product_url,
                "PRODUCT NAME": name,
                "PRICE": price_value,
                "CURRENCY": currency,
                "SELLER RATING": rating,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        if not scraped_data:
            return {"error": "No data scraped — possibly blocked or page didn’t render."}

        # ✅ Save safely to tmp
        save_to_excel("/tmp/Amazon", scraped_data)

        return {"data": scraped_data}

    except Exception as e:
        print(f"[Amazon Error] {e}")
        print(traceback.format_exc())
        return {"error": str(e)}

    finally:
        if close_after:
            quit_amazon_driver(driver)
