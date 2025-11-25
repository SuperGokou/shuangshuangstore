# update_shipping.py
import json
import requests
from bs4 import BeautifulSoup
import time
import os

# Define file path
JSON_FILE = 'data/shipping.json'

def update_tracking():
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found.")
        return

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Checking {len(data)} items...")

    for item in data:
        tracking_code = item.get('tracking_number')
        phone = item.get('phone')
        
        # Skip if missing data
        if not tracking_code or not phone:
            continue

        url = f"https://www.junanex.com/tracking?code={tracking_code}&mobile={phone}"
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                rows = soup.find_all('tr')
                
                # Logic: Find the first row with 3 columns (Date | Status | Location/Details)
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) == 3 and '20' in cols[1].get_text():
                        # Found a valid history row
                        status_text = cols[2].get_text(strip=True)
                        date_text = cols[1].get_text(strip=True)
                        
                        # Update the JSON
                        item['status'] = f"{status_text} ({date_text})"
                        print(f"✅ Updated {tracking_code}: {status_text}")
                        break
            else:
                print(f"⚠️ Connection failed for {tracking_code}: {r.status_code}")
        except Exception as e:
            print(f"❌ Error {tracking_code}: {e}")
        
        # Sleep to be polite to the server
        time.sleep(1)

    # Save back to file
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("Done.")

if __name__ == "__main__":
    update_tracking()