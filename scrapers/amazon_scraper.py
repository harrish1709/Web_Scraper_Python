from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, random, re, os
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime


def scrape_amazon(query):
    # 🔹 Detect paths automatically (Hostinger may vary)
    chromium_path = "/usr/bin/chromium-browser"
    chromedriver_path = "/usr/bin/chromedriver"
    if not os.path.exists(chromium_path):
        chromium_path = "/usr/bin/chromium"
    if not os.path.exists(chromedriver_path):
        chromedriver_path = "/usr/lib/chromium-browser/chromedriver"

    # ✅ Configure Chrome options
    options = Options()
    options.add_argument("--headless=new")  # modern headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-default-apps")

    # 🧠 Randomize user-agent slightly
    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.7390.122 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.7390.122 Safari/537.36",
    ])
    options.add_argument(f"--user-agent={ua}")

    # 🧩 Explicit binary and driver paths
    options.binary_location = chromium_path
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)

    # 🕵️ Stealth tweaks (avoid headless detection)
    try:
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    try:
        polite_delay()
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        driver.get(url)

        # ✅ Wait dynamically for results to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
            )
        except:
            time.sleep(random.uniform(6, 9))  # fallback wait

        # Detect blocked/captcha pages
        html = driver.page_source
        if "To discuss automated access" in html or "Enter the characters you see below" in html:
            return {"error": "Blocked by Amazon (Robot Check). Try using a proxy or rotating IP."}

        soup = BeautifulSoup(html, "html.parser")
        product_cards = soup.select("div[data-component-type='s-search-result']")

        scraped_data = []

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
            price_nums = re.findall(r"[\\d,]+(?:\\.\\d+)?", raw_price)
            if not price_nums:
                continue
            price_value = float(price_nums[0].replace(",", ""))

            currency_match = re.search(r"([$€£₹]|Rs)", raw_price)
            currency = currency_match.group(0) if currency_match else "NA"

            # Rating
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
            return {"error": "No data scraped — possibly blocked or page didn’t render properly."}

        save_to_excel("Amazon_India", scraped_data)
        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
