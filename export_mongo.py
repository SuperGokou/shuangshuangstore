import json
from pymongo import MongoClient
from bson import ObjectId

# CONFIG
MONGO_URI = "mongodb+srv://mingxiaharvard_db_user:A9jYurFGiFadX4gJ@clienttracking.d4slkzd.mongodb.net/?appName=clientTracking"
DB_NAME = "tracking_db"

def serialize(obj):
    """Helper to fix MongoDB ObjectId errors"""
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj

def export_data():
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # 1. EXPORT PRODUCTS
    products = list(db.products.find({}, {'_id': 0})) # Exclude _id
    with open('data/products.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=4)
    print(f"📦 Exported {len(products)} products")

    # 2. EXPORT OUTGOING SHIPMENTS (JunAn)
    # We join with 'customers' to get the phone/address data
    shipments = list(db.outgoing_shipments.find())
    export_shipments = []
    
    for s in shipments:
        # If we need customer details that aren't in the shipment document
        if 'customer_id' in s:
            customer = db.customers.find_one({'_id': s['customer_id']})
            if customer:
                s['phone'] = customer.get('phone')
                s['address'] = customer.get('address')
                s['recipient'] = customer.get('name')
        
        # Clean up ObjectId
        s['_id'] = str(s['_id'])
        if 'customer_id' in s: s['customer_id'] = str(s['customer_id'])
        
        export_shipments.append(s)

    with open('data/shipping.json', 'w', encoding='utf-8') as f:
        json.dump(export_shipments, f, ensure_ascii=False, indent=4)
    print(f"✈️ Exported {len(export_shipments)} shipments")

    # 3. EXPORT INCOMING ORDERS
    orders = list(db.incoming_orders.find({}, {'_id': 0}))
    with open('data/orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=4)
    print(f"🚚 Exported {len(orders)} incoming orders")

if __name__ == "__main__":
    export_data()