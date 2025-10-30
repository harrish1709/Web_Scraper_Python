from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime

def scrape_ebay(query):
    options = Options()
    options.add_argument("--headless") # ✅ Run in headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/141.0.7390.122 Safari/537.36")

    # 🧠 Explicitly set the Chromium binary path
    options.binary_location = "/usr/bin/chromium-browser"

    # Start ChromeDriver with these options
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)

    try:
        polite_delay()
        url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}"
        driver.get(url)

        time.sleep(random.uniform(3, 6))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select("li.s-card")

        scraped_data = []

        for card in product_cards:
            url_tag = card.select_one("a.su-link")
            product_url = url_tag['href'] if url_tag else "N/A"

            name_tag = (
                card.select_one(".s-card__title") or card.select_one(".s-item__title")
            )
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            # Remove unwanted text fragments
            junk_words = [
                "shop on ebay", "open in new tab", "click to see price", 
                "see price", "ships for free", "free shipping", "sponsored"
            ]
            for junk in junk_words:
                name = re.sub(junk, "", name, flags=re.IGNORECASE)

            name = name.strip()
            if not name:
                continue
            
            price_tag = (
                card.select_one(".s-card__price")
            )
            price_text_raw = price_tag.get_text(" ", strip=True) if price_tag else "NA"

            price_nums = re.findall(r'[\d,]+(?:\.\d+)?', price_text_raw)
            if not price_nums:
                continue
            price_value = int(float(price_nums[0].replace(",", ""))) if price_nums else "NA"

            currency_match = re.search(r'([$€£₹])|([A-Z]{3})', price_text_raw)
            currency = currency_match.group(0) if currency_match else "NA" 

            card_text = card.get_text(" ", strip=True)
            rating_match = re.search(r'\d{1,3}(?:\.\d+)?%\s*positive(?:\s*\(\d+\))?', card_text, re.IGNORECASE)
            rating_text = rating_match.group(0) if rating_match else "N/A"

            scraped_data.append({
                "SOURCE URL": product_url,
                "PRODUCT NAME": name,
                "PRICE": price_value,
                "CURRENCY": currency,
                "SELLER RATING": rating_text,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        if not scraped_data:
            return {"error": "No data scraped — page may have loaded incorrectly or no items matched."}

        save_to_excel("eBay", scraped_data)
        return{"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}
    finally:
        driver.quit()