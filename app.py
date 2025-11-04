from flask import Flask, render_template, request
import pandas as pd
from scrapers.amazon_scraper import scrape_amazon
from scrapers.flipkart_scraper import scrape_flipkart
from scrapers.ebay_scraper import scrape_ebay
from scrapers.snapdeal_scraper import scrape_snapdeal

app = Flask(__name__)

SCRAPERS = {
    "amazon": scrape_amazon,
    "flipkart": scrape_flipkart,
    "ebay": scrape_ebay,
    "snapdeal": scrape_snapdeal
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
            file = request.files.get("file")

            # --- Bulk Upload ---
            if file and file.filename:
                df = pd.read_excel(file) if file.filename.endswith(".xlsx") else pd.read_csv(file)

                for _, row in df.iterrows():
                    brand = str(row.get("Brand", "")).strip()
                    product = str(row.get("Product", "")).strip()
                    site = str(row.get("Website Name", "")).lower().strip()
                    oem = str(row.get("OEM Number", "")).strip()
                    asin = str(row.get("ASIN Number", "")).strip()

                    # Skip rows missing required fields
                    if not brand or not product:
                        continue

                    sites_to_scrape = SCRAPERS.keys() if not site else [site]

                    for site_name in sites_to_scrape:
                        if site_name not in SCRAPERS:
                            continue
                        scraper = SCRAPERS[site_name]
                        data = scraper(brand, product, oem, asin)

                        if "error" not in data:
                            for d in data["data"]:
                                d["WEBSITE"] = site_name.capitalize()
                                results.append(d)
                        else:
                            error = data["error"]

            # --- Manual Input ---
            else:
                # Require brand and product for manual entry
                if not brand or not product:
                    error = "Both Brand and Product fields are required."
                else:
                    sites_to_scrape = SCRAPERS.keys() if not website else [website]

                    for site in sites_to_scrape:
                        if site not in SCRAPERS:
                            continue
                        scraper = SCRAPERS[site]
                        data = scraper(brand, product, oem_number, asin_number)

                        if "error" in data:
                            error = data["error"]
                        else:
                            for d in data["data"]:
                                d["WEBSITE"] = site.capitalize()
                                results.append(d)

            # --- If nothing scraped and no explicit error ---
            if not results and not error:
                error = "No results found. Please check your input or try again later."

        except Exception as e:
            error = f"Error: {str(e)}"

    return render_template("index.html", results=results, error=error)

if __name__ == "__main__":
    app.run(debug=True)
