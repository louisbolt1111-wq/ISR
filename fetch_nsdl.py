import requests
import pandas as pd
from bs4 import BeautifulSoup
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_latest_nsdl_fpi():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Crawl NSDL's official FPI Fortnightly Selection & Latest Reports pages for actual links
    index_urls = [
        "https://nsdl.co.in",
        "https://nsdl.co.in"
    ]

    found_links = []
    for index_url in index_urls:
        try:
            r = requests.get(index_url, headers=headers, timeout=20, verify=False)
            print(f"Checked {index_url} -> Status: {r.status_code}")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "Fortnightly" in href or "FIIInvestSector" in href or href.endswith(".html"):
                        full_url = href if href.startswith("http") else f"https://nsdl.co.in{href.lstrip('/')}"
                        if full_url not in found_links:
                            found_links.append(full_url)
        except Exception as e:
            print(f"Error accessing {index_url}: {e}")

    print(f"Found {len(found_links)} candidate report links: {found_links[:4]}")

    extracted_tables = []
    for url in found_links[:3]:
        try:
            resp = requests.get(url, headers=headers, timeout=20, verify=False)
            if resp.status_code == 200:
                tables = pd.read_html(resp.text)
                if tables:
                    df = max(tables, key=len)
                    df["Source_URL"] = url
                    extracted_tables.append(df)
                    print(f"Successfully parsed table from {url} ({len(df)} rows)")
        except Exception as e:
            print(f"Could not parse {url}: {e}")

    if extracted_tables:
        combined = pd.concat(extracted_tables, ignore_index=True)
        combined.to_csv("nsdl_fpi_latest.csv", index=False)
        print("SUCCESS: Saved nsdl_fpi_latest.csv")
    else:
        # Create a status placeholder so GitHub Actions never crashes with exit code 128
        pd.DataFrame([{"Status": "NSDL server unreachable from cloud IP; use manual upload in Tab 2"}]).to_csv("nsdl_fpi_latest.csv", index=False)
        print("Created placeholder CSV because NSDL blocked or timed out.")

if __name__ == "__main__":
    get_latest_nsdl_fpi()
