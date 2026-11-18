import requests
import pandas as pd
from datetime import datetime
import calendar
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_latest_nsdl_fpi():
    today = datetime.today()
    candidate_dates = []

    for months_back in range(0, 4):
        year = today.year if today.month - months_back > 0 else today.year - 1
        month = (today.month - months_back - 1) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]

        for day in [last_day, 15]:
            dt = datetime(year, month, day)
            if dt <= today:
                candidate_dates.append(dt.strftime("%b%d%Y"))

    candidate_dates = sorted(list(set(candidate_dates)), key=lambda x: datetime.strptime(x, "%b%d%Y"), reverse=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://nsdl.co.in"
    }

    extracted_tables = []

    for date_str in candidate_dates:
        urls = [
            f"https://nsdl.co.in_{date_str}.html",
            f"https://nsdl.co.in_{date_str}.html"
        ]
        for url in urls:
            try:
                resp = requests.get(url, headers=headers, timeout=20, verify=False)
                if resp.status_code == 200 and len(resp.text) > 1000:
                    tables = pd.read_html(resp.text)
                    if tables:
                        df = max(tables, key=len)
                        df["Report_Date"] = date_str
                        extracted_tables.append(df)
                        print(f"Fetched NSDL report for {date_str}")
                        break
            except Exception as e:
                print(f"Failed {url}: {e}")
                continue
        if len(extracted_tables) == 2:
            break

    if extracted_tables:
        combined = pd.concat(extracted_tables, ignore_index=True)
        combined.to_csv("nsdl_fpi_latest.csv", index=False)
        print("Saved nsdl_fpi_latest.csv successfully.")
    else:
        print("No NSDL tables could be retrieved from candidate URLs.")

if __name__ == "__main__":
    get_latest_nsdl_fpi()
