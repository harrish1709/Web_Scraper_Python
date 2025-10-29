import random, time
import pandas as pd
import os
os.makedirs("static", exist_ok=True)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0'
]

def get_headers():
    return {'User-Agent': random.choice(USER_AGENTS)}

def polite_delay():
    time.sleep(random.uniform(5, 15))

def save_to_excel(site_name, data):
    df = pd.DataFrame(data)
    df_unsorted = df
    df_sorted = df.sort_values(by='PRICE')

    unsorted_path = f"static/{site_name}_Unsorted.xlsx"
    sorted_path = f"static/{site_name}_Sorted.xlsx"

    df_unsorted.to_excel(unsorted_path, index=False)
    df_sorted.to_excel(sorted_path, index=False)

    return {
        "unsorted_file": unsorted_path,
        "sorted_file": sorted_path,
        "data": df_sorted.to_dict(orient="records"),
        "count": len(df_sorted)
    }