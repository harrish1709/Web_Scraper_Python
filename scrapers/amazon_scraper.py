import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, random, re, os
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime
import traceback
import json

# Small pool of realistic UAs (rotate)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    # add more if desired
]

def _stealth_hook(driver, user_agent):
    """
    Apply runtime JS tweaks to reduce detection surface.
    Keep this minimal and targeted.
    """
    try:
        # set languages
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});")
        # plugins
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});")
        # webdriver flag
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        # chrome runtime (some checks)
        driver.execute_script(
            "window.chrome = { runtime: {},  // minimal chrome object\n  loadTimes: function(){return {}} };"
        )
        # permissions mock
        driver.execute_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.__query = originalQuery;
            window.navigator.permissions.query = (parameters) => (
              parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
        # override userAgent via navigator (in addition to options)
        driver.execute_script(f"Object.defineProperty(navigator, 'userAgent', {{get: () => '{user_agent}'}});")
    except Exception:
        # don't fail if any tweak errors
        pass

def _random_viewport_size():
    widths = [1200, 1366, 1440, 1600, 1920]
    heights = [800, 768, 900, 1024, 1080]
    return random.choice(widths), random.choice(heights)

def scrape_amazon(brand, product):
    """
    Scrape Amazon.in search results using undetected_chromedriver with stealth tweaks.
    Returns dict: {"data": [...]} or {"error": "msg"}
    """
    max_retries = 3
    headless = True
    scraped_data = []
    oem_number=None
    asin_number=None

    for attempt in range(1, max_retries + 1):
        ua = random.choice(USER_AGENTS)
        width, height = _random_viewport_size()

        try:
            options = uc.ChromeOptions()
            # headless mode: undetected-chromedriver supports 'headless=new' in newer chrome
            if headless:
                options.add_argument("--headless=new")
            # common safe flags
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-agent={ua}")
            options.add_argument(f"--window-size={width},{height}")
            # less suspicious: disable extensions not needed
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-networking")
            # minimal logging
            options.add_argument("--log-level=3")

            # If your VPS has chrome binary in a non-standard path, set options.binary_location before Chrome() call:
            # options.binary_location = "/usr/bin/chromium-browser"

            driver = uc.Chrome(options=options)  # uc will manage driver binary
            driver.set_page_load_timeout(45)

            # apply stealth hook to overwrite some navigator properties
            _stealth_hook(driver, ua)

            # small human-like warmup navigation
            try:
                driver.get("https://www.amazon.in/")
                time.sleep(random.uniform(1.2, 2.8))
                # Accept possible consent popups by attempting to click common selectors (non-fatal)
                try:
                    # site-specific, safe to ignore if not present
                    for selector in ["#sp-cc-accept", "input[name='accept']"]:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, selector)
                            el.click()
                            time.sleep(0.5)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                # ignore warmup failures
                pass

            # polite delay before searching
            polite_delay()

            # 🧩 Build simplified search URL (only brand + product)
            query = "+".join([k for k in [brand, product] if k])
            search_url = f"https://www.amazon.in/s?k={query}"
   
            driver.get(search_url)

            # wait dynamic search results
            try:
                WebDriverWait(driver, 18).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except Exception:
                # fallback: small scroll & wait for render
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
                except Exception:
                    pass
                time.sleep(random.uniform(4.5, 8.5))

            html = driver.page_source

            # quick robot/captcha detection
            if "Enter the characters you see below" in html or "To discuss automated access to Amazon" in html or "automated access" in html:
                # blocked — close and retry with a new UA and slight backoff
                driver.quit()
                sleep_for = random.uniform(6, 14) * attempt
                time.sleep(sleep_for)
                continue

            # parse with the exact selectors you provided originally
            soup = BeautifulSoup(html, "html.parser")
            product_cards = soup.select("div[data-component-type='s-search-result']")

            for card in product_cards:
                # URL
                url_tag = card.select_one(
                    "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal"
                ) or card.select_one("a.a-link-normal.s-no-outline")
                product_url = "https://www.amazon.in" + url_tag["href"] if url_tag else "N/A"

                # Product name
                name_tag = card.select_one(
                    "h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal"
                ) or card.select_one("h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal")
                name = name_tag.get_text(strip=True) if name_tag else "N/A"

                # Price
                price_tag = card.select_one("span.a-price > span.a-offscreen") or card.select_one("span.a-color-price")
                raw_price = price_tag.text.strip() if price_tag else "NA"

                price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
                if not price_nums:
                    continue
                price_value = int(float(price_nums[0].replace(",", ""))) if price_nums else "NA"

                currency_match = re.search(
                   r'(?:'
                   r'[\$€£₹¥₩₽₺₫₴₦₱₵₲₡₸₭₣₥₧₯₰₳₢₣₤₥₦₧₩₫₭₮₯₱₲₳₴₺₼₾₿]|'  # Common currency symbols
                   r'د\.إ|ر\.س|ج\.م|₨|'                   # Arabic-region symbols (AED, SAR, EGP, PKR, etc.)
                   r'[A-Z]{3}'                            # ISO 4217 codes (USD, AED, EUR, etc.)
                   r')',
                   raw_price
                )
                currency = currency_match.group(0) if currency_match else "NA"

                # Rating
                rating_tag = card.select_one("span.a-icon-alt")
                rating = (
                    rating_tag.get_text(strip=True).replace("out of 5 stars", "").strip() if rating_tag else "N/A"
                )

                scraped_data.append({
                        "BRAND": brand,
                        "PRODUCT": product,
                        "OEM NUMBER": oem_number or "NA",
                        "ASIN NUMBER": asin_number or "NA",
                        "WEBSITE": "Amazon",
                        "PRODUCT NAME": name,
                        "PRICE": price_value,
                        "CURRENCY": currency,
                        "SELLER RATING": rating,
                        "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "SOURCE URL": product_url,
                    })

            # if scraped_data found, persist and return
            if scraped_data:
                try:
                    save_to_excel("Amazon", scraped_data)
                except Exception:
                    # don't fail the scrape if saving errors
                    pass
                driver.quit()
                return {"data": scraped_data}
            else:
                # no items found — possible render issue; retry
                driver.quit()
                time.sleep(random.uniform(4, 10))
                continue

        except Exception as e:
            # attempt failed, log and retry
            try:
                traceback.print_exc()
            except Exception:
                pass
            try:
                driver.quit()
            except Exception:
                pass
            time.sleep(random.uniform(4, 12) * attempt)
            continue

    # all attempts exhausted
    return {"error": "Blocked or failed after retries — consider using proxies or a scraping API for higher reliability."}
