from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime

def scrape_flipkart(brand, product, oem_number=None, asin_number=None):
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

        # 🧩 Build dynamic query
        if asin_number:
            keywords = [brand, product, asin_number]
        else:
            keywords = [brand, product, oem_number] if oem_number else [brand, product]

        query = "+".join([k for k in keywords if k])
        url = f"https://www.flipkart.com/search?q={query}"
        driver.get(url)

        # Wait for dynamic content
        time.sleep(random.uniform(3, 6))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select("div[data-id]")

        scraped_data = []

        for card in product_cards:
            # Product URL
            url_tag = (
                card.select_one("a.wjcEIp") or
                card.select_one("a.KzDlHZ") or
                card.select_one("a.WKTcLC.BwBZTg") or
                card.select_one("a.CGtC98") or
                card.select_one("a.VJA4J3") or
                card.select_one("a.WKTcLC")
            )
            product_url = "https://www.flipkart.com" + url_tag['href'] if url_tag and url_tag.has_attr("href") else "N/A"

            # Product Name
            name_tag = (
                card.select_one("a.wjcEIp") or
                card.select_one("div.KzDlHZ") or
                card.select_one("a.WKTcLC.BwBZTg") or
                card.select_one("a.VJA4J3") or
                card.select_one("a.WKTcLC") or
                card.select_one("div.kv0tEm")
            )
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            if not name or name.lower() in ["sponsored", "advertisement"]:
                continue

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

            try:
                price_value = float(price_nums[0].replace(",", ""))
            except ValueError:
                continue

            currency_match = re.search(r'([$€£₹]|Rs)', raw_price)
            currency = currency_match.group(0) if currency_match else "₹"

            # Rating
            rating_tag = (
                card.select_one("div.XQDdHH") or
                card.select_one("div._3LWZlK") or
                card.select_one("span.Y1HWO0") or
                card.select_one("div._2_R_DZ")
            )
            rating = rating_tag.text.strip() if rating_tag else "N/A"

            # Append structured data
            scraped_data.append({
                "BRAND": brand,
                "PRODUCT": product,
                "OEM NUMBER": oem_number or "NA",
                "ASIN NUMBER": asin_number or "NA",
                "WEBSITE": "Flipkart",
                "PRODUCT NAME": name,
                "PRICE": price_value,
                "CURRENCY": currency,
                "SELLER RATING": rating,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "SOURCE URL": product_url,
            })

        if not scraped_data:
            return {"error": "No data scraped — page may have loaded incorrectly or no items matched."}

        try:
            save_to_excel("Flipkart", scraped_data)
        except Exception:
            pass

        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
