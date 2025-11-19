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

AMAZON_DOMAINS = [
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it",
    "amazon.es", "amazon.ca", "amazon.in", "amazon.com.mx", "amazon.com.br",
    "amazon.com.au", "amazon.ae", "amazon.sa", "amazon.sg", "amazon.nl",
    "amazon.se", "amazon.pl", "amazon.co.jp", "amazon.cn"
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


def scrape_amazon(brand, product):
    max_retries = 3
    headless = True
    scraped_data = []
    oem_number = None
    asin_number = None

    selected_domain = os.environ.get("SELECTED_AMAZON_DOMAIN", "").strip() or None
    domains_to_try = [selected_domain] if selected_domain else AMAZON_DOMAINS

    for domain in domains_to_try:
        for attempt in range(1, max_retries + 1):
            ua = random.choice(USER_AGENTS)
            width, height = _random_viewport_size()

            try:
                options = uc.ChromeOptions()
                if headless:
                    options.add_argument("--headless+new")
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    options.add_argument("--disable-gpu")
                    options.add_argument("--disable-blink-features=AutomationControlled")
                    options.add_argument(f"--user-agent={ua}")
                    options.add_argument(f"--window-size={width},{height}")
                    options.add_argument("--disable-extensions")
                    options.add_argument("--disable-background-networking")
                    options.add_argument("--log-level=3")

                driver = uc.Chrome(options=options)
                driver.set_page_load_timeout(45)

                _stealth_hook(driver, ua)

                try:
                    warmup_url = f"https://www.{domain}/"
                    driver.get(warmup_url)
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

                query = "+".join([k for k in [brand, product] if k])
                search_url = f"https://www.{domain}/s?k={query}"

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

                # Captcha or block detection
                if (
                    "Enter the characters you see below" in html
                    or "automated access" in html
                    or "To discuss automated access to Amazon" in html
                ):
                    driver.quit()
                    time.sleep(random.uniform(6, 14) * attempt)
                    continue

                soup = BeautifulSoup(html, "html.parser")
                product_cards = soup.select("div[data-component-type='s-search-result']")

                for card in product_cards:
                    # Product URL
                    url_tag = card.select_one(
                        "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal"
                    ) or card.select_one("a.a-link-normal.s-no-outline")
                    product_url = f"https://www.{domain}" + url_tag["href"] if url_tag else "N/A"

                    # Product name
                    name_tag = card.select_one(
                        "h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal"
                    ) or card.select_one("h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal")
                    name = name_tag.get_text(strip=True) if name_tag else "N/A"

                    # Price
                    price_tag = card.select_one("span.a-price > span.a-offscreen") or card.select_one("span.a-color-price")
                    raw_price = price_tag.text.strip() if price_tag else "NA"

                    # --- Universal Amazon price parser ---
                    if raw_price and raw_price != "NA":
                        raw = raw_price.strip()
                        raw = raw.replace("\xa0", "").replace(" ", "")
                        raw = re.sub(r'[^\d.,]', '', raw)

                        if re.search(r',\d{2}$', raw):  # e.g. "1.299,99" or "3,49"
                            raw = raw.replace(".", "").replace(",", ".")
                        else:
                            raw = raw.replace(",", "")

                        match = re.search(r'\d+(?:\.\d+)?', raw)
                        price_value = round(float(match.group(0)),2) if match else "NA"
                    else:
                        price_value = "NA"

                    if price_value == "NA":
                        continue

                    currency_match = re.search(
                        r'(?:'
                        r'[\$€£₹¥₩₽₺₫₴₦₱₵₲₡₸₭₣₥₧₯₰₳₢₣₤₥₦₧₩₫₭₮₯₱₲₳₴₺₼₾₿]|'  # Common currency symbols
                        r'د\.إ|ر\.س|ج\.م|₨|'                          # Arabic / Indian symbols
                        r'S\$|zł|kr|R\$|'                             # Singapore, Poland, Sweden, Brazil
                        r'[A-Z]{3}'                                   # ISO codes like USD, AED, INR
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
                        "WEBSITE": f"Amazon ({domain})",
                        "PRODUCT NAME": name,
                        "PRICE": price_value,
                        "CURRENCY": currency,
                        "SELLER RATING": rating,
                        "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "SOURCE URL": product_url,
                    })

                if scraped_data:
                    try:
                        save_to_excel("Amazon", scraped_data)
                    except Exception:
                        pass
                    driver.quit()
                    return {"data": scraped_data}
                else:
                    driver.quit()
                    time.sleep(random.uniform(4, 10))
                    continue

            except Exception as e:
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

    return {
        "error": "Blocked or failed after multiple retries — consider rotating proxies or using a scraping API."
    }
