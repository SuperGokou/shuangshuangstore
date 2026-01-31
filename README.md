# 觉觉在北美 — Shuangshuang Store

Inventory and order management dashboard for a cross-border e-commerce business, coordinating product stock between the US and China.

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
