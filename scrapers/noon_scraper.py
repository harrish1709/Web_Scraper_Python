import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time, re
from datetime import datetime
from scrapers.utils import polite_delay, save_to_excel
import random

def scrape_noon(brand, product, oem_number=None, asin_number=None):

    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Random User Agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
    ]
    
    options.add_argument(f"--user-agent={random.choice(user_agents)}")


    driver = uc.Chrome(options=options)

    try:

        polite_delay()

        # Build search query
        if asin_number:
            keywords = [brand, product, asin_number]
        else:
            keywords = [brand, product, oem_number] if oem_number else [brand, product]

        query = "+".join([k for k in keywords if k])
        url = f"https://www.noon.com/uae-en/search/?q={query}"
        driver.get(url)

        time.sleep(5)

        # Smooth scroll — required for Noon
        for _ in range(30):
            driver.execute_script("window.scrollBy(0, 900);")
            time.sleep(0.6)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Product cards
        product_cards = soup.select('div[class*="linkWrapper"]')

        scraped_data = []

        for card in product_cards:

            # URL
            link = card.select_one('a[class*="productBoxLink"], a[href*="/p/"]')
            product_url = "https://www.noon.com" + link["href"] if link else "N/A"

            # Name
            name_tag = card.select_one('[data-qa="plp-product-box-name"], h2[data-qa="plp-product-box-name"]')
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            # Rating
            rating_tag = card.select_one('div[class*="textCtr"]')
            rating = rating_tag.get_text(strip=True) if rating_tag else "N/A"

            # Price
            price_tag = card.select_one('strong[class*="amount"]')
            raw_price = price_tag.get_text(strip=True) if price_tag else "0"

            price_nums = re.findall(r'[\d,]+(?:\.\d+)?', raw_price)
            price_value = float(price_nums[0].replace(",", "")) if price_nums else 0

            # Currency
            currency_tag = card.select_one('span[class*="currency"], span[class*="isCurrencySymbol"]')
            currency = currency_tag.get_text(strip=True) if currency_tag else "AED"

            scraped_data.append({
                "BRAND": brand,
                "PRODUCT": product,
                "OEM NUMBER": oem_number or "NA",
                "ASIN NUMBER": asin_number or "NA",
                "WEBSITE": "Noon",
                "PRODUCT NAME": name,
                "PRICE": price_value,
                "CURRENCY": currency,
                "SELLER RATING": rating,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "SOURCE URL": product_url,
            })

        if not scraped_data:
            return {"error": "Selectors matched 0 products — but this set SHOULD work."}

        try:
            save_to_excel("Noon", scraped_data)
        except:
            pass

        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
