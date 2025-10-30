from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime

def scrape_amazon(query):
    options = Options()
    # ✅ Modern headless mode
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    # 🧠 Hide Selenium traces
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 🔒 Strong user-agent
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.6261.128 Safari/537.36"
    )

    # ✅ Chromium & ChromeDriver paths (for Ubuntu)
    options.binary_location = "/usr/bin/chromium-browser"
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)

    # 🚫 Remove webdriver flag
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    try:
        polite_delay()
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        driver.get(url)

        # 🧩 Check for CAPTCHA
        if "robot check" in driver.page_source.lower() or "captcha" in driver.page_source.lower():
            return {"error": "Amazon CAPTCHA triggered — try again after 5–10 mins."}

        # Wait until product cards load
        timeout = time.time() + 15
        product_cards = []
        while time.time() < timeout:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            product_cards = soup.select("div[data-component-type='s-search-result']")
            if product_cards:
                break
            time.sleep(1)

        if not product_cards:
            return {"error": "No data scraped — page may have loaded incorrectly or was blocked."}

        scraped_data = []

        for card in product_cards:
            # Product URL
            url_tag = card.select_one(
                "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal, "
                "a.a-link-normal.s-no-outline"
            )
            product_url = "https://www.amazon.in" + url_tag["href"] if url_tag else "N/A"

            # Product Name
            name_tag = card.select_one(
                "h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal, "
                "h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal"
            )
            name = name_tag.get_text(strip=True) if name_tag else "N/A"
            name = re.sub(r"(sponsored|deal of the day|click to see price)", "", name, flags=re.I).strip()

            # Price
            price_tag = card.select_one("span.a-price > span.a-offscreen") or card.select_one("span.a-color-price")
            raw_price = price_tag.text.strip() if price_tag else "NA"
            price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
            if not price_nums:
                continue
            price_value = float(price_nums[0].replace(",", ""))
            currency_match = re.search(r'([$€£₹]|Rs)', raw_price)
            currency = currency_match.group(0) if currency_match else "₹"

            # Rating
            rating_tag = card.select_one("span.a-icon-alt")
            rating = (
                rating_tag.get_text(strip=True)
                .replace("out of 5 stars", "")
                .strip()
                if rating_tag else "N/A"
            )

            scraped_data.append({
                "SOURCE URL": product_url,
                "PRODUCT NAME": name,
                "PRICE": price_value,
                "CURRENCY": currency,
                "SELLER RATING": rating,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        if not scraped_data:
            return {"error": "No valid products found after filtering."}

        save_to_excel("Amazon_India", scraped_data)
        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
        
