import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime
import random

def scrape_westmarine(brand, product, oem_number=None, asin_number=None):
    # Start undetected Chrome (headless OK!)
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    # Random User Agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
    ]
    
    options.add_argument(f"--user-agent={random.choice(user_agents)}")


    driver = uc.Chrome(version_main=141, options=options)

    try:
        polite_delay()

        # Build search query
        if asin_number:
            keywords = [brand, product, asin_number]
        else:
            keywords = [brand, product, oem_number] if oem_number else [brand, product]

        query = "+".join([k for k in keywords if k])
        url = f"https://www.westmarine.com/search?q={query}&lang=en_US"
        driver.get(url)

        # GIVE ALGOLIA JS TIME TO LOAD RENDERED RESULTS
        time.sleep(5)

        # Ensure further JS rendering is complete
        for _ in range(5):
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

        # Parse
        product_cards = driver.find_elements("css selector", "div.product")

        scraped_data = []
        
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

        if not scraped_data:
            return {"error": "No products found. JS may not have loaded fully."}

        # Save to Excel
        try:
            save_to_excel("WestMarine", scraped_data)
        except:
            pass

        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
