import json
import requests
import time
import os

# Define file path
JSON_FILE = 'data/shipping.json'

def scrape_junan_status(tracking_number, phone): # Renamed for consistency
    url = "https://www.junanex.com/tracking"
    payload = {
        't': 'query_code',
        'code': tracking_number,
        'mobile': phone  # Matches the argument above
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        # Use POST to talk to the API
        response = requests.post(url, data=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            # Check if the API returned success
            if data.get('success'):
                history_list = data.get('message', [])
                if history_list:
                    # Logic from your snippet: take the latest entry
                    latest_entry = history_list[0]
                    
                    # Your logic: Get the last key (latest status)
                    # Note: Depending on JunAn's structure, we might need the value or the key.
                    # Assuming your snippet is correct and the status is the key.
                    if isinstance(latest_entry, dict):
                        keys = list(latest_entry.keys())
                        if keys:
                            return keys[-1] # Returns the status text
                    
                    # Fallback if entry is just a string or different format
                    return str(latest_entry)

            return "Check Website (No Data)"
        return f"Connection Failed ({response.status_code})"
    
    except Exception as e:
        print(f"Scraper Error for {tracking_number}: {e}")
        return "Update Failed"

def update_tracking():
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found.")
        return

    # 1. Read the current JSON
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Checking {len(data)} items...")

    # 2. Loop through and update
    for item in data:
        tracking_code = item.get('tracking_number')
        phone = item.get('phone')
        
        # Skip if missing data
        if not tracking_code or not phone:
            continue

        print(f"Checking {tracking_code}...")
        
        # Call the new API scraper function
        new_status = scrape_junan_status(tracking_code, phone)
        
        # Update the item status
        item['status'] = new_status
        print(f"  -> Status: {new_status}")
        
        # Sleep to be polite to the server
        time.sleep(1)

    # 3. Save back to file
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("Done. shipping.json updated.")

if __name__ == "__main__":
    update_tracking()