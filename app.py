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
        brand = request.form.get("brand", "").strip()
        website = request.form.get("website", "").lower()
        file = request.files.get("file")

        if file:
            df = pd.read_excel(file) if file.filename.endswith(".xlsx") else pd.read_csv(file)
            df = df.dropna(subset=["Brand", "Website Name"])
            results = []
            
            for site, rows in df.groupby("Website Name"):
                site = site.lower().strip()
                if site not in SCRAPERS:
                    continue
            
                print(f"Scraping {site} for {len(rows)} brands")
                brands = [str(b).strip() for b in rows["Brand"].tolist() if str(b).strip()]
                try:
                    # reuse one driver per site
                    scraper_func = SCRAPERS[site]
                    for brand in brands:
                        data = scraper_func(brand)
                        if "data" in data:
                            for d in data["data"]:
                                d["WEBSITE"] = site.capitalize()
                                results.append(d)
                        polite_delay()
                except Exception as e:
                    print(f"Error on {site}: {e}")
                    continue

    return render_template("index.html", results=results, error=error)


if __name__ == "__main__":
    app.run(debug=True)
