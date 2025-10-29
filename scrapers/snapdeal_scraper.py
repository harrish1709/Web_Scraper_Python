from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime


def scrape_snapdeal(query):
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        polite_delay()
        url = f"https://www.snapdeal.com/search?keyword={query.replace(' ', '%20')}"
        driver.get(url)

        # Wait for dynamic content to load
        time.sleep(random.uniform(5, 10))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select(".product-tuple-listing")

        scraped_data = []

        for card in product_cards:
            # Product URL
            url_tag = card.select_one("a.dp-widget-link, a.dp-widget-link.noUdLine")
            product_url = url_tag['href'] if url_tag else "N/A"

            # Product name
            name_tag = card.select_one(".product-title")
            name = name_tag.get_text(strip=True) if name_tag else "N/A"

            # Price extraction
            price_tag = (
                card.select_one("span.lfloat.product-price")
                or card.select_one("span[id^='display-price']")
                or card.select_one(".product-price > span")
            )

            if price_tag:
                # Prefer data-price attribute (clean number)
                if price_tag.has_attr("data-price"):
                    price = price_tag["data-price"].strip()
                else:
                    raw_price = price_tag.get_text(strip=True)
                    price = re.sub(r"[^\d.]", "", raw_price)
            else:
                price = "0"

            # --- CURRENCY ---
            currency_match = re.search(r"(Rs\.?|₹|[$€£])", price_tag.text if price_tag else "")
            currency = currency_match.group(0) if currency_match else "NA"

            # Rating (based on filled-stars width)
            rating_tag = card.select_one(".filled-stars")
            if rating_tag and "width" in rating_tag.attrs.get("style", ""):
                try:
                    width = float(rating_tag["style"].split(":")[1].replace("%", "").strip())
                    rating = f"{round(width / 20, 1)}"
                except:
                    rating = "N/A"
            else:
                rating = "N/A"

            try:
                price = int(float(price))
            except:
                continue

            scraped_data.append({
                "SOURCE URL": product_url,
                "PRODUCT NAME": name,
                "PRICE": price,
                "CURRENCY": currency,
                "SELLER RATING": rating,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        if not scraped_data:
            return {"error": "No data scraped — page may have loaded incorrectly or no items matched."}

        save_to_excel("Snapdeal", scraped_data)
        return{"data": scraped_data}
    
    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()