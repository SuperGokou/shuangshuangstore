# 觉觉在北美 - Shuangshuang Store

Inventory and order management dashboard for a cross-border e-commerce business, coordinating product stock between the US and China.

## Features

- **Inventory Dashboard** — Real-time stock levels across multiple locations (US signed/unsigned, shipped to China)
- **Shipment Tracking** — JunAn Express integration with customer details and delivery status
- **Order Management** — Purchase order history with color-coded status (Fulfilled, Partial, Pending)
- **Inventory Statistics** — Product shipment stats with packaging variant breakdowns
- **Auto-Update** — GitHub Actions workflow runs every 2 hours to refresh tracking and inventory data
- **Responsive Design** — Mobile-friendly layout

## Tech Stack

- **Frontend:** HTML, CSS, vanilla JavaScript
- **Backend:** Python, MongoDB
- **Data:** JSON files (`data/`) synced from MongoDB via `export_mongo.py`
- **CI/CD:** GitHub Actions

## Project Structure

```
├── index.html              # Main dashboard
├── pages/
│   ├── login.html          # Admin login
│   └── clients.html        # Client management
├── css/style.css           # Styles
├── data/                   # JSON data files
│   ├── products.json
│   ├── orders.json
│   ├── shipping.json
│   ├── purchase_orders.json
│   └── stats.json
├── export_mongo.py         # MongoDB → JSON export script
├── update_shipping.py      # Shipping info updater
└── .github/workflows/      # Automated update workflows
```

## Setup

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Set the `MONGO_URI` environment variable for database access.
3. Run `python export_mongo.py` to export data to JSON.
4. Open `index.html` in a browser.
