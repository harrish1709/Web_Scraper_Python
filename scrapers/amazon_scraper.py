from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime

def scrape_amazon(query):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64)...Firefox/126.0"
    ]
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    options.binary_location = "/usr/bin/chromium-browser"
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)

    try:
        polite_delay()
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        driver.get(url)
        time.sleep(random.uniform(4, 6))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(3, 5))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select("div[data-component-type='s-search-result'], div.s-card-container")

        scraped_data = []
        for card in product_cards:
            url_tag = (
                card.select_one("a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal")
                or card.select_one("a.a-link-normal.s-no-outline")
                or card.select_one("a.a-link-normal")
            )
            product_url = "https://www.amazon.in" + url_tag["href"] if url_tag else "N/A"

            name_tag = (
                card.select_one("h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal")
                or card.select_one("h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal")
            )
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            price_tag = card.select_one("span.a-price > span.a-offscreen") or card.select_one("span.a-color-price")
            raw_price = price_tag.text.strip() if price_tag else "NA"
            price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
            if not price_nums:
                continue
            price_value = float(price_nums[0].replace(",", ""))

            currency_match = re.search(r'([$€£₹]|Rs)', raw_price)
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
            return {"error": "No data scraped — page may have loaded incorrectly or no items matched."}

        save_to_excel("Amazon_India", scraped_data)
        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
        
