from flask import Flask, render_template, request
import pandas as pd
import traceback
from scrapers.amazon_scraper import scrape_amazon, init_amazon_driver, quit_amazon_driver
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
            website = request.form.get("website", "").lower()
            file = request.files.get("file")

            # Bulk file upload
            if file:
                df = pd.read_excel(file) if file.filename.endswith(".xlsx") else pd.read_csv(file)

                # ✅ Create shared Amazon driver if needed
                amazon_driver = None
                if "amazon" in df["Website Name"].str.lower().values:
                    amazon_driver = init_amazon_driver()

                for _, row in df.iterrows():
                    try:
                        brand = str(row.get("Brand", "")).strip()
                        site = str(row.get("Website Name", "")).lower().strip()
                        if not brand or site not in SCRAPERS:
                            continue

                        scraper = SCRAPERS[site]

                        if site == "amazon":
                            data = scraper(brand, driver=amazon_driver)
                        else:
                            data = scraper(brand)

                        if "error" not in data:
                            for d in data["data"]:
                                d["WEBSITE"] = site.capitalize()
                                results.append(d)
                    except Exception as e:
                        print(f"[ERROR] Row failed ({brand} - {site}): {e}")
                        print(traceback.format_exc())

                if amazon_driver:
                    quit_amazon_driver(amazon_driver)

            # Single search
            elif brand and website in SCRAPERS:
                scraper = SCRAPERS[website]
                data = scraper(brand)
                if "error" in data:
                    error = data["error"]
                else:
                    for d in data["data"]:
                        d["WEBSITE"] = website.capitalize()
                        results.append(d)
            else:
                error = "Please provide valid input or upload a valid file."

        except Exception as e:
            error = f"Internal Error: {str(e)}"
            print(traceback.format_exc())

    return render_template("index.html", results=results, error=error)


if __name__ == "__main__":
    app.run(debug=True)
