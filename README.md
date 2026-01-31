# 觉觉在北美 — Shuangshuang Store

## About

Shuangshuang Store (觉觉在北美) is a web-based inventory management system for a cross-border e-commerce business that collects limited-edition and collectible cups and drinkware in the United States — including brands like Stanley, LoveShackFancy collaborations, and other hard-to-find releases — and ships them to buyers who want them but can't easily purchase from the original retailers.

The business sources products from multiple US retailers, consolidates them domestically, and forwards shipments internationally via JunAn Express (君安快递). Managing this workflow involves tracking products through several stages: purchasing from US retailers, confirming delivery in the US (signed/unsigned), consolidating orders, and shipping packages to their final destination.

This dashboard provides a single interface to:

- **Monitor stock** across all stages — how many units have been signed for in the US, how many are awaiting signature, and how many have been shipped to China
- **Track purchases** from multiple suppliers with per-item details, images, tracking numbers from FedEx/UPS, and delivery confirmation checkboxes
- **Manage shipments** through JunAn Express with real-time tracking status, recipient details, weight, and addresses
- **Analyze business performance** with charts showing stock distribution, shipment volume by product, source supplier comparisons, and inventory turnover metrics
- **Track shipping finances** with a monthly cost/deposit/refund breakdown and wallet balance

Data is stored in MongoDB and automatically exported to static JSON files every 2 hours via GitHub Actions, keeping the dashboard up to date without manual intervention.

## Features

### Dashboard
- **Metric Cards** — US Signed, US Unsigned, In Transit to China, Total Stock with click-to-filter
- **Interactive Filter** — Click any metric card to switch the orders table to a filtered product view with images, sorted by the selected metric
- **Order Tracking** — Scrollable incoming orders table with source, status badges, tracking numbers, and signed status
- **Shipping Cost Chart** — 6-month financial overview (运费/支付/退款) with summary stats and wallet balance

### Inventory
- **Multi-View** — Table, grid, and list views with search and sort
- **Stock Status** — Automatic In Stock / Low Stock / Out of Stock badges
- **Shipment Statistics** — Per-product breakdown of packaged vs. unpackaged shipments
- **Export** — CSV export for all inventory data

### Purchase Orders
- **Full History** — Date, source, product items with images, tracking numbers, and notes
- **Sign Tracking** — Checkbox per shipment to mark as signed (persisted in localStorage)
- **Search & Export** — Filter and export all purchase orders

### Shipments
- **Live Tracking** — JunAn Express integration with tracking links, weight, and delivery status
- **Recipient Management** — Phone, address (truncated), and status badges

### Analytics
- **KPI Cards** — Total items shipped, orders, avg items/order, inventory turnover with trend indicators
- **Charts** — Stock by product (bar), category distribution (pie), shipment volume, source performance

### General
- **Auto-Update** — GitHub Actions workflow runs every 2 hours to refresh tracking and inventory data
- **Responsive Design** — Mobile-friendly sidebar with hamburger menu, adaptive grids

## Tech Stack

- **Frontend:** HTML, CSS, vanilla JavaScript (`js/app.js`)
- **Backend:** Python, MongoDB
- **Data:** JSON files (`data/`) synced from MongoDB via `export_mongo.py`
- **CI/CD:** GitHub Actions

## Project Structure

```
├── index.html              # Main dashboard (HTML only)
├── js/app.js               # All application logic
├── css/style.css           # Styles + utility classes
├── pages/
│   ├── login.html          # Admin login
│   └── clients.html        # Client management
├── data/                   # JSON data files
│   ├── products.json       # Product inventory
│   ├── orders.json         # Order tracking
│   ├── shipping.json       # Shipment details
│   ├── purchase_orders.json# Purchase history
│   └── stats.json          # Shipment statistics
├── img/                    # Product images
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
