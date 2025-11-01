# Keep module-level imports that are lightweight
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, random, re, os
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime
import traceback
import json

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
]

def _stealth_hook(driver, user_agent):
    try:
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});")
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        driver.execute_script(
            "window.chrome = { runtime: {},  loadTimes: function(){return {}} };"
        )
        driver.execute_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.__query = originalQuery;
            window.navigator.permissions.query = (parameters) => (
              parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
        driver.execute_script(f"Object.defineProperty(navigator, 'userAgent', {{get: () => '{user_agent}'}});")
    except Exception:
        pass

def _random_viewport_size():
    widths = [1200, 1366, 1440, 1600, 1920]
    heights = [800, 768, 900, 1024, 1080]
    return random.choice(widths), random.choice(heights)

def scrape_amazon(query, max_retries: int = 3, headless: bool = True):
    """
    Safer scrape_amazon:
    - A: import undetected_chromedriver inside function (defers import)
    - B: initialize driver = None and guard quit calls
    - C: return friendly errors instead of crashing the worker
    """
    # A: import inside the function to avoid import-time crashes in Gunicorn workers
    try:
        import undetected_chromedriver as uc
    except ModuleNotFoundError as e:
        # Helpful message if UC or a dependency is missing
        return {"error": "undetected_chromedriver not available in environment: " + str(e)}
    except Exception as e:
        return {"error": "Failed to import undetected_chromedriver: " + str(e)}

    scraped_data = []
    driver = None  # B: ensure driver exists in this scope for safe cleanup

    for attempt in range(1, max_retries + 1):
        ua = random.choice(USER_AGENTS)
        width, height = _random_viewport_size()
        try:
            options = uc.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-agent={ua}")
            options.add_argument(f"--window-size={width},{height}")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-networking")
            options.add_argument("--log-level=3")

            # Try to create driver, but handle creation failure gracefully
            try:
                driver = uc.Chrome(options=options)
            except Exception as e:
                # If driver init fails, log and return helpful error (don't crash worker)
                traceback.print_exc()
                return {"error": f"Chrome driver init failed: {e}"}

            driver.set_page_load_timeout(45)

            _stealth_hook(driver, ua)

            # Warmup navigation (non-fatal)
            try:
                driver.get("https://www.amazon.in/")
                time.sleep(random.uniform(1.2, 2.8))
                for selector in ["#sp-cc-accept", "input[name='accept']"]:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, selector)
                        el.click()
                        time.sleep(0.5)
                    except Exception:
                        pass
            except Exception:
                pass

            polite_delay()

            search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
            driver.get(search_url)

            try:
                WebDriverWait(driver, 18).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except Exception:
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
                except Exception:
                    pass
                time.sleep(random.uniform(4.5, 8.5))

            html = driver.page_source

            if "Enter the characters you see below" in html or "To discuss automated access to Amazon" in html or "automated access" in html:
                # blocked — close and retry with new UA/backoff
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
                time.sleep(random.uniform(6, 14) * attempt)
                continue

            soup = BeautifulSoup(html, "html.parser")
            product_cards = soup.select("div[data-component-type='s-search-result']")

            for card in product_cards:
                try:
                    url_tag = card.select_one(
                        "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal"
                    ) or card.select_one("a.a-link-normal.s-no-outline")
                    product_url = "https://www.amazon.in" + url_tag["href"] if url_tag else "N/A"

                    name_tag = card.select_one(
                        "h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal"
                    ) or card.select_one("h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal")
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
                except Exception:
                    # Skip faulty card but keep scraping others
                    continue

            if scraped_data:
                try:
                    save_to_excel("Amazon", scraped_data)
                except Exception:
                    pass
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
                return {"data": scraped_data}
            else:
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
                time.sleep(random.uniform(4, 10))
                continue

        except Exception as e:
            # Log full traceback but do not let exception crash the worker.
            try:
                traceback.print_exc()
            except Exception:
                pass
            # Ensure driver is closed if it exists
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            driver = None
            time.sleep(random.uniform(4, 12) * attempt)
            continue

    # all retries exhausted
    return {"error": "Blocked or failed after retries — consider using proxies or a scraping API for higher reliability."}
