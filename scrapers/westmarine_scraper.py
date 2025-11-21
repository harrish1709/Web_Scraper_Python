import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, random, re, traceback
from datetime import datetime
from scrapers.utils import polite_delay, save_to_excel


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
]


def _random_viewport_size():
    widths = [1200, 1366, 1440, 1600, 1920]
    heights = [800, 768, 900, 1024, 1080]
    return random.choice(widths), random.choice(heights)


def _human_scroll(driver, passes=8):
    for _ in range(passes):
        driver.execute_script("window.scrollBy(0, arguments[0]);", random.randint(300, 900))
        time.sleep(random.uniform(0.6, 1.2))


def scrape_westmarine(brand, product, oem_number=None, asin_number=None, headless=True, max_retries=3):
    scraped_data = []

    query_terms = [t for t in [brand, product, oem_number, asin_number] if t]
    query = "+".join(query_terms)
    search_url = f"https://www.westmarine.com/search?q={query}&lang=en_US"

    for attempt in range(1, max_retries + 1):

        ua = random.choice(USER_AGENTS)
        width, height = _random_viewport_size()

        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={ua}")
        options.add_argument(f"--window-size={width},{height}")

        driver = None

        try:
            driver = uc.Chrome(options=options)
            driver.set_page_load_timeout(45)

            # Warmup & cookie acceptance
            try:
                driver.get("https://www.westmarine.com/")
                time.sleep(random.uniform(1.2, 2.0))
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, "#onetrust-accept-btn-handler")
                    btn.click()
                    time.sleep(0.5)
                except:
                    pass
            except:
                pass

            polite_delay()

            # Perform search
            driver.get(search_url)

            # Wait for JS-rendered products
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.product"))
                )
            except:
                _human_scroll(driver)
                time.sleep(2)

            _human_scroll(driver, passes=10)
            time.sleep(1.5)

            product_cards = driver.find_elements(By.CSS_SELECTOR, "div.product")

            for card in product_cards:
                # Product URL + Name
                try:
                    a = card.find_element(By.CSS_SELECTOR, "a.link.font-weight-medium")
                    product_url = a.get_attribute("href")
                    name = a.text.strip()
                except:
                    continue

                # Price
                try:
                    price_raw = card.find_element(By.CSS_SELECTOR, "span.item-price").text
                except:
                    price_raw = "0"

                nums = re.findall(r"[\d.,]+", price_raw)
                price_value = float(nums[0].replace(",", "")) if nums else 0.0

                # Rating
                try:
                    rating_block = card.find_element(By.CSS_SELECTOR, "div.refinebar-rating-options-container").text
                    match = re.search(r"\(([\d.]+)\)", rating_block)
                    rating = match.group(1) if match else "N/A"
                except:
                    rating = "N/A"

                scraped_data.append({
                    "BRAND": brand,
                    "PRODUCT": product,
                    "OEM NUMBER": oem_number or "NA",
                    "ASIN NUMBER": asin_number or "NA",
                    "WEBSITE": "WestMarine",
                    "PRODUCT NAME": name,
                    "PRICE": price_value,
                    "CURRENCY": "$",
                    "SELLER RATING": rating,
                    "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOURCE URL": product_url,
                })

            if scraped_data:
                try:
                    save_to_excel("WestMarine", scraped_data)
                except:
                    pass

                driver.quit()
                return {"data": scraped_data}

            # no results → retry
            driver.quit()
            time.sleep(3 * attempt)
            continue

        except Exception as e:
            traceback.print_exc()
            if driver:
                try: driver.quit()
                except: pass
            time.sleep(4 * attempt)
            continue

    return {"error": "WestMarine blocked or no results after retries."}
