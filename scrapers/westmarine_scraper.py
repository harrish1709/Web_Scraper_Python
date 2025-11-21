import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, random, re, traceback
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
]

def _stealth_hook(driver, user_agent):
    try:
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});")
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        driver.execute_script("window.chrome = { runtime: {}, loadTimes: function(){return {}} };")
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

def _human_scroll(driver, passes=8, pause_min=0.9, pause_max=1.6):
    """Small incremental scrolling to trigger lazy hydration."""
    for _ in range(passes):
        try:
            x = random.randint(300, 900)
            driver.execute_script(f"window.scrollBy(0, {x});")
        except Exception:
            pass
        time.sleep(random.uniform(pause_min, pause_max))

def scrape_westmarine(brand, product, oem_number=None, asin_number=None, headless=True, max_retries=3):
    scraped_data = []
    
    for attempt in range(1, max_retries + 1):
        ua = random.choice(USER_AGENTS)
        width, height = _random_viewport_size()

        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument(f"--user-agent={ua}")
        options.add_argument(f"--window-size={width},{height}")
        options.add_argument("--disable-background-networking")
        options.add_argument("--log-level=3")

        driver = None
        try:
            driver = uc.Chrome(options=options)
            driver.set_page_load_timeout(60)

            _stealth_hook(driver, ua)

            # optional warmup to let cookies / consent popups appear
            try:
                driver.get("https://www.westmarine.com/")
                time.sleep(random.uniform(1.0, 2.5))
                # close or accept cookie banners if present (best effort)
                for sel in ["button#onetrust-accept-btn-handler", "button[title='Accept']"]:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        el.click()
                        time.sleep(0.4)
                    except Exception:
                        pass
            except Exception:
                pass

            polite_delay()

            # Build search query (lean on brand/product/oem)
            query_terms = [t for t in [brand, product, oem_number, asin_number] if t]
            query = "+".join(query_terms)
            search_url = f"https://www.westmarine.com/search?q={query}&lang=en_US"
            driver.get(search_url)

            # Wait for the product grid or some sign of JS-rendered content
            try:
                WebDriverWait(driver, 18).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.product"))
                )
            except Exception:
                # perform human-like scroll and wait more if initial wait fails
                _human_scroll(driver, passes=6)
                time.sleep(random.uniform(2.5, 5.0))

            # perform several scroll passes to allow lazy-hydration to trigger
            _human_scroll(driver, passes=10, pause_min=0.9, pause_max=1.3)

            # ensure final DOM is settled
            time.sleep(random.uniform(1.2, 2.0))

            html = driver.page_source

            block_indicators = [
                "automated access", "Please verify you are a human", "CAPTCHA", "Enter the characters you see below"
            ]
            if any(s.lower() in html.lower() for s in block_indicators):
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(random.uniform(6, 16) * attempt)
                continue

            soup = BeautifulSoup(html, "html.parser")
            product_cards = soup.select("div.product")

            for card in product_cards:
                # Product URL
                try:
                    url_tag = card.find_element("css selector", "a.link.font-weight-medium")
                    product_url = url_tag.get_attribute("href")
                    name = url_tag.text.strip()
                except:
                    product_url = "N/A"
                    name = "N/A"
            
                # Price
                try:
                    price_tag = card.find_element("css selector", "span.item-price")
                    raw_price = price_tag.text.strip()
                except:
                    raw_price = "0"
            
                # Convert price
                price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
                price_value = float(price_nums[0].replace(",", "")) if price_nums else 0
    
                currency="$"
            
                # Rating
                try:
                    rating_tag = card.find_element("css selector", "div.refinebar-rating-options-container")
                    match = re.search(r"\(([\d\.]+)\)", rating_tag.text)
                    rating = match.group(1) if match else "N/A"
                except:
                    rating = "N/A"
    
                scraped_data.append({
                    "BRAND": brand,
                    "PRODUCT": product,
                    "OEM NUMBER": oem_number or "NA",
                    "ASIN NUMBER": asin_number or "NA",
                    "WEBSITE": "AmitRetail",
                    "PRODUCT NAME": name,
                    "PRICE": price_value,
                    "CURRENCY": currency,
                    "SELLER RATING": rating,
                    "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOURCE URL": product_url,
                })
                
                if scraped_data:
                    try:
                        save_to_excel("WestMarine", scraped_data)
                    except Exception:
                        pass
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    return {"data": scraped_data}
    
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(random.uniform(4, 10) * attempt)
                continue
    
            except Exception as e:
                try:
                    traceback.print_exc()
                except Exception:
                    pass
                try:
                    if driver:
                        driver.quit()
                except Exception:
                    pass
                time.sleep(random.uniform(3, 10) * attempt)
                continue
    
        return {
            "error": "Blocked or failed after multiple retries — consider rotating proxies, using residential proxies, or reducing headless stealth (set headless=False)."
        }
