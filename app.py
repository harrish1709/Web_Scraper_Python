from flask import Flask, render_template, request
import pandas as pd
from scrapers.amazon_scraper import scrape_amazon
from scrapers.flipkart_scraper import scrape_flipkart
from scrapers.ebay_scraper import scrape_ebay
from scrapers.snapdeal_scraper import scrape_snapdeal
from scrapers.amitretail_scraper import scrape_amitretail
from scrapers.noon_scraper import scrape_noon
from scrapers.sharafdg_scraper import scrape_sharafdg
from scrapers.westmarine_scraper import scrape_westmarine
import time, random, os

app = Flask(__name__)

selected_amazon_domain = None

SCRAPERS = {
    "amazon": scrape_amazon,
    "flipkart": scrape_flipkart,
    "ebay": scrape_ebay,
    "snapdeal": scrape_snapdeal,
    "amitretail":scrape_amitretail,
    "noon":scrape_noon,
    "sharafdg":scrape_sharafdg,
    "westmarine":scrape_westmarine
}

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    error = None

    if request.method == "POST":
        try:
            brand = request.form.get("brand", "").strip()
            product = request.form.get("product", "").strip()
            website = request.form.get("website", "").lower().strip()
            oem_number = request.form.get("oem_number", "").strip()
            asin_number = request.form.get("asin_number", "").strip()
            amazon_country = request.form.get("amazon_country", "amazon.com").strip()
            if not amazon_country:
                amazon_country = "amazon.com"
            file = request.files.get("file")

            # ✅ Always store the user's Amazon country selection globally
            os.environ["SELECTED_AMAZON_DOMAIN"] = amazon_country

            # --- Bulk Upload ---
            if file and file.filename:
                df = pd.read_excel(file) if file.filename.endswith(".xlsx") else pd.read_csv(file)

                for _, row in df.iterrows():
                    brand = str(row.get("Brand", "")).strip()
                    product = str(row.get("Product", "")).strip()
                    site = str(row.get("Website Name", "")).lower().strip()
                    oem = str(row.get("OEM Number", "")).strip()
                    asin = str(row.get("ASIN Number", "")).strip()

                    if not brand or not product:
                        continue

                    # If "All Websites" is selected, scrape all except Amazon uses selected domain
                    sites_to_scrape = SCRAPERS.keys() if not site else [site]

                    for site_name in sites_to_scrape:
                        if site_name not in SCRAPERS:
                            continue
                        scraper = SCRAPERS[site_name]

                        if site_name == "amazon":
                            os.environ["SELECTED_AMAZON_DOMAIN"] = amazon_country
                            data = scraper(brand, product)
                        else:
                            data = scraper(brand, product, oem, asin)

                        if "error" not in data:
                            for d in data["data"]:
                                d["WEBSITE"] = site_name.capitalize()
                                results.append(d)
                        else:
                            error = data["error"]

                        if site_name == "amazon":
                            time.sleep(random.uniform(10, 25))

            # --- Manual Input ---
            else:
                if not brand or not product:
                    error = "Both Brand and Product fields are required."
                else:
                    sites_to_scrape = SCRAPERS.keys() if website in ("", "allwebsite") else [website]

                    for site in sites_to_scrape:
                        if site not in SCRAPERS:
                            continue

                        scraper = SCRAPERS[site]

                        # Set Amazon domain if provided
                        if site == "amazon":
                            os.environ["SELECTED_AMAZON_DOMAIN"] = amazon_country
                            print(f"🟡 Using Amazon domain: {os.environ.get('SELECTED_AMAZON_DOMAIN')}")
                            data = scraper(brand, product)
                        else:
                            data = scraper(brand, product, oem_number, asin_number)

                        # Handle errors or append data
                        if "error" in data:
                            error = data["error"]
                        else:
                            for d in data["data"]:
                                d["WEBSITE"] = site.capitalize()
                                results.append(d)

            if not results and not error:
                error = "No results found. Please check your input or try again later."

        except Exception as e:
            error = f"Error: {str(e)}"

    return render_template("index.html", results=results, error=error)

if __name__ == "__main__":
    app.run(debug=True)
