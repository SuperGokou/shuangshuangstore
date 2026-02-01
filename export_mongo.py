import json
import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, date

# CONFIG
# Load .env file if present (for local development)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("MONGO_DB_NAME", "tracking_db")


def export_data():
    try:
        client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
        db = client[DB_NAME]
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # --- HELPER: Fix Date & ID Errors ---
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.strftime("%Y-%m-%d")  # Format date as YYYY-MM-DD
        if isinstance(obj, ObjectId):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    # 1. EXPORT PRODUCTS
    products = list(db.products.find({}, {'_id': 0}))  # Exclude _id
    with open('data/products.json', 'w', encoding='utf-8') as f:
        # Added default=json_serial
        json.dump(products, f, ensure_ascii=False, indent=4, default=json_serial)
    print(f"📦 Exported {len(products)} products")

    # 2. EXPORT OUTGOING SHIPMENTS (JunAn)
    # We join with 'customers' to get the phone/address data
    shipments = list(db.outgoing_shipments.find())
    export_shipments = []

    for s in shipments:
        # Join with 'customers' only to fill MISSING data
        if 'customer_id' in s:
            customer = db.customers.find_one({'_id': s['customer_id']})
            if customer:
                # Only use customer profile data if shipment data is missing
                if 'phone' not in s or not s['phone']:
                    s['phone'] = customer.get('phone')
                
                # CRITICAL FIX: Do NOT overwrite the shipment address if it already exists
                if 'address' not in s or not s['address']:
                    s['address'] = customer.get('address')
                
                if 'recipient' not in s or not s['recipient']:
                    s['recipient'] = customer.get('name')
        
        # Clean up ObjectId
        s['_id'] = str(s['_id'])
        if 'customer_id' in s: s['customer_id'] = str(s['customer_id'])
        
        export_shipments.append(s)

    with open('data/shipping.json', 'w', encoding='utf-8') as f:
        json.dump(export_shipments, f, ensure_ascii=False, indent=4, default=json_serial)
    print(f"✈️ Exported {len(export_shipments)} shipments")

    # 3. EXPORT INCOMING ORDERS
    orders = list(db.incoming_orders.find({}, {'_id': 0}))
    with open('data/orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=4, default=json_serial)
    print(f"🚚 Exported {len(orders)} incoming orders")

    # 4. EXPORT STATS
    stats = list(db.product_stats.find({}, {'_id': 0}))
    with open('data/stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=4, default=json_serial)
    print(f"📊 Exported {len(stats)} stats to data/stats.json")

    # 5. EXPORT PURCHASE ORDERS
    # We sort by date (descending) so newest orders show first
    purchase_orders = list(db.purchase_orders.find({}, {'_id': 0}).sort("date", -1))

    with open('data/purchase_orders.json', 'w', encoding='utf-8') as f:
        json.dump(purchase_orders, f, ensure_ascii=False, indent=4, default=json_serial)
    print(f"🛍️ Exported {len(purchase_orders)} purchase orders to data/purchase_orders.json")


if __name__ == "__main__":
    export_data()