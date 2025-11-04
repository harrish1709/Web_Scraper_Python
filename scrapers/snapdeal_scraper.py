from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time, random, re
from scrapers.utils import polite_delay, save_to_excel
from datetime import datetime


def scrape_snapdeal(brand, product, oem_number=None, asin_number=None):
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

        # ---- Build dynamic search query ----
        if asin_number:
            keywords = [brand, product, asin_number]
        else:
            keywords = [brand, product, oem_number] if oem_number else [brand, product]

        query = "%20".join([k for k in keywords if k])
        url = f"https://www.snapdeal.com/search?keyword={query}"

        driver.get(url)

        # Wait for dynamic content
        time.sleep(random.uniform(5, 10))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select(".product-tuple-listing")

        scraped_data = []

        # ---- Parse product listings ----
        for card in product_cards:
            # Product URL
            url_tag = card.select_one("a.dp-widget-link, a.dp-widget-link.noUdLine")
            product_url = url_tag["href"] if url_tag else "N/A"

            # Product Name
            name_tag = card.select_one(".product-title")
            name = name_tag.get_text(strip=True) if name_tag else "N/A"
            if not name or name.lower() in ["sponsored", "advertisement"]:
                continue

            # ---- Price ----
            price_tag = (
                card.select_one("span.lfloat.product-price") or
                card.select_one("span[id^='display-price']") or
                card.select_one(".product-price > span")
            )

            if price_tag:
                if price_tag.has_attr("data-price"):
                    price_text = price_tag["data-price"].strip()
                else:
                    price_text = re.sub(r"[^\d.]", "", price_tag.get_text(strip=True))
            else:
                price_text = "0"

            try:
                price_value = int(float(price_text))
            except ValueError:
                continue

            # ---- Currency ----
            currency_match = re.search(r"(Rs\.?|₹|[$€£])", price_tag.text if price_tag else "")
            currency = currency_match.group(0) if currency_match else "₹"

            # ---- Rating ----
            rating_tag = card.select_one(".filled-stars")
            if rating_tag and "width" in rating_tag.attrs.get("style", ""):
                try:
                    width = float(rating_tag["style"].split(":")[1].replace("%", "").strip())
                    rating = f"{round(width / 20, 1)}"
                except Exception:
                    rating = "N/A"
            else:
                rating = "N/A"

            # ---- Append structured data ----
            scraped_data.append({
                "BRAND": brand,
                "PRODUCT": product,
                "OEM NUMBER": oem_number or "NA",
                "ASIN NUMBER": asin_number or "NA",
                "WEBSITE": "Snapdeal",
                "PRODUCT NAME": name,
                "PRICE": price_value,
                "CURRENCY": currency,
                "SELLER RATING": rating,
                "DATE SCRAPED": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "SOURCE URL": product_url,
            })

        # ---- Validation ----
        if not scraped_data:
            return {"error": "No data scraped — page may have loaded incorrectly or no items matched."}

        # ---- Save and Return ----
        try:
            save_to_excel("Snapdeal", scraped_data)
        except Exception:
            pass

        return {"data": scraped_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        driver.quit()
