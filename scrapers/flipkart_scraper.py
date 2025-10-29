from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime

def scrape_flipkart(query):
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
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        driver.get(url)

        # Allow time for dynamic content to load
        time.sleep(random.uniform(3, 6))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select("div[data-id]")

        scraped_data = []

        for card in product_cards:
             # URL and Name
            url_tag = (
                card.select_one("a.wjcEIp") or  # Common for product tiles
                card.select_one("a.KzDlHZ") or
                card.select_one("a.WKTcLC.BwBZTg") or
                card.select_one("a.CGtC98") or
                card.select_one("a.VJA4J3") or
                card.select_one("a.WKTcLC")
            )
            product_url = "https://www.flipkart.com" + url_tag['href'] if url_tag and url_tag.has_attr("href") else "N/A"
            name = url_tag.get_text(strip=True) if url_tag else "N/A"

            # Price
            price_tag = (
                card.select_one("div.Nx9bqj") or
                card.select_one("div._30jeq3") or
                card.select_one("div._1_WHN1") or
                card.select_one("div._16Jk6d")
            )
            raw_price = price_tag.text.strip() if price_tag else "0"

            price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
            if not price_nums:
                continue
            price_value = float(price_nums[0].replace(",", "")) if price_nums else "NA"

            currency_match = re.search(r'([$€£₹]|Rs)', raw_price)
            currency = currency_match.group(0) if currency_match else "NA"

            price = re.sub(r"[^\d.]", "", raw_price)

            # Rating
            rating_tag = (
                card.select_one("div.XQDdHH") or
                card.select_one("div._3LWZlK") or
                card.select_one("span._1lRcqv") or
                card.select_one("div._2_R_DZ")
            )
            rating = rating_tag.text.strip() if rating_tag else "N/A"

            try:
                price = int(float(price))
            except:
                continue

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

        save_to_excel("Flipkart", scraped_data)
        return{"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}
    finally:
        driver.quit()