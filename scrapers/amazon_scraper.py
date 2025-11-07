import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, random, re, traceback
from datetime import datetime
from scrapers.utils import polite_delay, save_to_excel

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
]

AMAZON_DOMAINS = {
    "IN": "www.amazon.in",
    "US": "www.amazon.com",
    "AE": "www.amazon.ae",
    "SA": "www.amazon.sa",
    "UK": "www.amazon.co.uk",
    "DE": "www.amazon.de",
    "FR": "www.amazon.fr",
    "IT": "www.amazon.it",
    "ES": "www.amazon.es",
    "JP": "www.amazon.co.jp",
    "CA": "www.amazon.ca",
    "AU": "www.amazon.com.au",
    "BR": "www.amazon.com.br",
    "MX": "www.amazon.mx",
    "NL": "www.amazon.nl",
    "SE": "www.amazon.se",
    "SG": "www.amazon.sg",
    "TR": "www.amazon.com.tr",
    "PL": "www.amazon.pl",
}

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
              parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters)
            );
        """)
        driver.execute_script(f"Object.defineProperty(navigator, 'userAgent', {{get: () => '{user_agent}'}});")
    except Exception:
        pass

def _random_viewport_size():
    widths = [1200, 1366, 1440, 1600, 1920]
    heights = [800, 768, 900, 1024, 1080]
    return random.choice(widths), random.choice(heights)

def _is_blocked_html(html):
    checks = [
        "Enter the characters you see below",
        "To discuss automated access to Amazon",
        "automated access",
        "Bot Check",
        "Type the characters you see in the image below",
        "<title>Robot Check</title>",
    ]
    lower = html.lower()
    return any(ch.lower() in lower for ch in checks)

def scrape_amazon(country_code, brand, product):
    scraped_data = []
    oem_number = asin_number = None
    max_retries = 3
    headless = True

    host = AMAZON_DOMAINS.get(country_code.upper(), "www.amazon.com")
    base_url = f"https://{host}"

    for attempt in range(1, max_retries + 1):
        ua = random.choice(USER_AGENTS)
        width, height = _random_viewport_size()
        driver = None

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

            driver = uc.Chrome(options=options)
            driver.set_page_load_timeout(60)

            _stealth_hook(driver, ua)

            # Warmup navigation and optional consent click
            try:
                driver.get(base_url + "/")
                time.sleep(random.uniform(1.2, 2.8))
                for selector in ["#sp-cc-accept", "input[name='accept']"]:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, selector)
                        el.click()
                        time.sleep(0.4)
                    except Exception:
                        pass
            except Exception:
                # ignore warmup problems
                pass

            polite_delay()

            query = "+".join([k for k in [brand, product] if k])
            search_url = f"{base_url}/s?k={query}"
            # log for debugging
            # print("Attempt", attempt, "URL:", search_url, "UA:", ua)

            driver.get(search_url)

            # robust wait: wait for either results or short delay/timing out
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except Exception:
                # fallback small JS scroll + wait
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
                except Exception:
                    pass
                time.sleep(random.uniform(4.5, 8.5))

            html = driver.page_source or ""
            # Save a copy for debugging if you want:
            # open(f"debug_amazon_{country_code}_{attempt}.html", "w", encoding="utf-8").write(html[:100000])

            if _is_blocked_html(html):
                # blocked — close and retry with backoff
                try:
                    driver.quit()
                except Exception:
                    pass
                sleep_for = random.uniform(6, 14) * attempt
                time.sleep(sleep_for)
                continue

            soup = BeautifulSoup(html, "html.parser")
            product_cards = soup.select("div[data-component-type='s-search-result']")
            for card in product_cards:
                url_tag = card.select_one("a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal") \
                          or card.select_one("a.a-link-normal.s-no-outline")
                product_url = base_url + url_tag["href"] if (url_tag and url_tag.get("href")) else "N/A"

                name_tag = card.select_one("h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal") \
                           or card.select_one("h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal")
                name = name_tag.get_text(strip=True) if name_tag else "N/A"

                price_tag = card.select_one("span.a-price > span.a-offscreen") or card.select_one("span.a-color-price")
                raw_price = price_tag.text.strip() if price_tag else "NA"
                price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
                if not price_nums:
                    # skip items without price (optional)
                    continue
                try:
                    price_value = int(float(price_nums[0].replace(",", "")))
                except Exception:
                    continue

                currency_match = re.search(
                    r'(?:[\$€£₹¥₩₽₺₫₴₦₱₵₲₡₸₭₣₥₧₯₰₳₢]|د\.إ|ر\.س|ج\.م|₨|[A-Z]{3})', raw_price
                )
                currency_symbol = currency_match.group(0) if currency_match else "NA"

                rating_tag = card.select_one("span.a-icon-alt")
                rating = rating_tag.get_text(strip=True).replace("out of 5 stars", "").strip() if rating_tag else "N/A"

                scraped_data.append({
                    "BRAND": brand,
                    "PRODUCT": product,
                    "OEM NUMBER": oem_number or "NA",
                    "ASIN NUMBER": asin_number or "NA",
                    "WEBSITE": host,
                    "PRODUCT NAME": name,
                    "PRICE": price_value,
                    "CURRENCY": currency_symbol,
                    "SELLER RATING": rating,
                    "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOURCE URL": product_url,
                })

            # success branch
            if scraped_data:
                try:
                    save_to_excel(f"Amazon_{country_code.upper()}", scraped_data)
                except Exception:
                    pass
                try:
                    driver.quit()
                except Exception:
                    pass
                return {"data": scraped_data}
            else:
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(random.uniform(4, 10))
                continue

        except Exception:
            traceback.print_exc()
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            # progressive backoff
            time.sleep(random.uniform(4, 12) * attempt)
            continue

    return {"error": f"Blocked or failed after {max_retries} retries for {host}"}
