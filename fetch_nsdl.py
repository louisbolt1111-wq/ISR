import requests
import pandas as pd
from datetime import datetime
import calendar

def get_latest_nsdl_fpi():
    today = datetime.today()
    candidate_dates = []

    for months_back in range(0, 3):
        year = (today.year if today.month - months_back > 0 else today.year - 1)
        month = (today.month - months_back - 1) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]

        for day in [last_day, 15]:
            dt = datetime(year, month, day)
            if dt <= today:
                candidate_dates.append(dt.strftime("%b%d%Y"))

    candidate_dates = sorted(list(set(candidate_dates)), key=lambda x: datetime.strptime(x, "%b%d%Y"), reverse=True)

    headers = {"User-Agent": "Mozilla/5.0"}
    extracted_tables = []

    for date_str in candidate_dates:
        url = f"https://nsdl.co.in_{date_str}.html"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                tables = pd.read_html(resp.text)
                if tables:
                    df = tables[0]
                    df["Report_Date"] = date_str
                    extracted_tables.append(df)
                    if len(extracted_tables) == 2:
                        break
        except Exception:
            continue

    if extracted_tables:
        combined = pd.concat(extracted_tables, ignore_index=True)
        combined.to_csv("nsdl_fpi_latest.csv", index=False)
        print("Saved NSDL FPI data successfully.")

if __name__ == "__main__":
    get_latest_nsdl_fpi()
