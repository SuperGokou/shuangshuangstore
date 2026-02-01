from pymongo import MongoClient
from bson.objectid import ObjectId
import re
import sys
import io
import os
import pandas as pd
import ast
from collections import defaultdict

# Fix emoji output on Windows consoles with GBK encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'gb18030', 'cp936'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# --- CONFIGURATION ---
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


# .fillna("") converts empty cells (floats) to empty strings (""), preventing the crash
products_data = pd.read_excel("data/products_data.xlsx").fillna("").to_dict(orient='records')
incoming_orders_data = pd.read_excel("data/incoming_orders_data.xlsx").fillna("").to_dict(orient='records')
shipping_data_raw = pd.read_excel("data/shipping_data.xlsx").fillna("").to_dict(orient='records')
inventory_stats_data = pd.read_excel("data/inventory_stats_data.xlsx").fillna("").to_dict(orient='records')
purchase_orders_raw = pd.read_excel("data/purchase_orders_data.xlsx").fillna("").to_dict(orient='records')
# Parse 'items' field from string to list
purchase_orders_data = []

for row in purchase_orders_raw:
    # If 'items' is a string looking like a list, parse it.
    if isinstance(row.get('items'), str):
        try:
            row['items'] = ast.literal_eval(row['items'])
        except (ValueError, SyntaxError):
            print(f"⚠️ Warning: Could not parse items for Order {row.get('order_id')}")
            row['items'] = []
    purchase_orders_data.append(row)


# ==========================================
# 2. LOGIC: CALCULATE STOCK & SHIPPED AUTOMATICALLY
# ==========================================

print("🔄 Recalculating Total Stock from Purchase Orders...")

# A. Tally up all purchase orders
# Structure: { "Product Name": { "total": 0, "signed": 0, "unsigned": 0 } }
stock_counts = {}

for order in purchase_orders_data:
    # 1. Determine if this order is "Signed" (Secured/Shipped) based on Note
    note = order.get('note', '')

    # LOGIC: If note contains "已发货" OR "已签收" -> Signed. Otherwise -> Unsigned.
    is_signed = "已发货" in note and "已签收" in note

    for item in order['items']:
        p_name = item['product'].replace(" (Gift Box)", "")
        qty = item['qty']

        # Normalize names to match products_data keys
        if p_name == "Flip Straw Tumbler 30 OZ Rose Quartz": p_name = "The IceFlow™ Flip Straw Tumbler 30 OZ Rose Quartz"

        # Initialize if not exists
        if p_name not in stock_counts:
            stock_counts[p_name] = {'total': 0, 'signed': 0, 'unsigned': 0}

        # Add Totals
        stock_counts[p_name]['total'] += qty

        if qty < 0:
            # It is a return.
            # Returns should reduce the 'Signed' (On Hand) stock, NOT 'Unsigned'.
            stock_counts[p_name]['signed'] += qty
        else:
            # It is a purchase (Positive Qty). Use standard logic.
            if is_signed:
                stock_counts[p_name]['signed'] += qty
            else:
                stock_counts[p_name]['unsigned'] += qty


# B. Calculate Shipped from Shipping Data (Outgoing)
def parse_shipping_details(details_str):
    """
    Parses a shipping details string and extracts product items, quantities, and packaging status.
    Returns: A list of tuples: (product_name, qty, is_packaged_bool)
    """
    items = []
    # 1. Standardize string format
    # Replace x/X with *, standardize brackets, remove spaces
    s = details_str.replace("x", "*").replace("X", "*").replace("（", "(").replace("）", ")").replace(" ", "")

    # 2. Product Name Mapping
    # Maps keywords to the canonical Product Name in your database
    name_map = {
        # 20oz Blue
        "20oz蓝": "蓝底 20oz", "蓝20oz": "蓝底 20oz", "蓝底20oz": "蓝底 20oz",
        # 40oz Blue
        "40oz蓝": "蓝底 40oz", "蓝40oz": "蓝底 40oz", "蓝底40oz": "蓝底 40oz", "40蓝": "蓝底 40oz",
        # 30oz Blue
        "30oz蓝": "蓝底 30oz", "蓝30oz": "蓝底 30oz", "蓝底30oz": "蓝底 30oz",
        # 20oz White
        "20oz白": "白底 20oz", "白20oz": "白底 20oz", "白底20oz": "白底 20oz",
        "30oz白": "白底 30oz", "白30oz": "白底 30oz", "白底30oz": "白底 30oz",
        # 40oz White
        "40oz白": "白底 40oz", "白40oz": "白底 40oz", "白底40oz": "白底 40oz", "40白": "白底 40oz",
        # 20oz pink
        "20oz粉": "粉底 20oz", "粉20oz": "粉底 20oz", "粉底20oz": "粉底 20oz",
        "40oz粉": "粉底 40oz", "粉40oz": "粉底 40oz", "粉底40oz": "粉底 40oz", "40粉": "粉底 40oz",
        # Slim Bottle
        "SlimBottle": "Slim Bottle", "Slim": "Slim Bottle",  # Spaceless due to earlier replace
        "礼盒": "礼盒",
        "HolidayReserveAllDayWineSet": "Holiday Reserve All Day Wine Set",
        "TheReserveWineTumblerSet|11oz": "The Reserve Wine Tumbler Set | 11 oz",
        "Everyday Camp Mug Set": "Everyday Camp Mug Set", "EverydayCampMugSet": "Everyday Camp Mug Set",
        "Holiday The Quencher Details ProTour Tumbler Set": "Holiday The Quencher Details ProTour Tumbler Set",
        "HolidayTheQuencherDetailsProTourTumblerSet": "Holiday The Quencher Details ProTour Tumbler Set",
        "Coquette Bow Chantilly 20oz": "Coquette Bow Chantilly 20oz", "CoquetteBowChantilly20oz": "Coquette Bow Chantilly 20oz",
        "情人节款20oz": "情人节款20oz", "情人节款30oz": "情人节款30oz", "情人节款40oz": "情人节款40oz",
        "情人节款红色20oz": "情人节款红色20oz", "情人节款红色30oz": "情人节款红色30oz", "情人节款红色40oz": "情人节款红色40oz",
    }

    # 3. Handle Parentheses Groups
    # We replace '+' inside parentheses with '&' to split safely later
    temp_s = ""
    depth = 0
    for char in s:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if char == '+' and depth > 0:
            temp_s += '&'
        else:
            temp_s += char

    parts = temp_s.split('+')

    # 4. Handle Special "Packaging Only" item
    if "压扁包装" in s:
        match = re.search(r'(\d+)\*?压扁包装', s)
        qty = int(match.group(1)) if match else 1
        items.append(("压扁包装", qty, True))

        # 5. Process each part
    for part in parts:
        part = part.strip()
        if not part: continue

        mult = 1
        content = part

        # Extract multiplier (e.g., "3*...")
        if '*' in part:
            try:
                m_str, _content = part.split('*', 1)
                mult = int(m_str)
                content = _content
            except:
                pass

        content = content.replace('&', '+')

        # --- Helper to process a single item string ---
        def process_single_item(item_str, multiplier):
            # A. Check for Packaging Keyword
            is_pkg = "包装" in item_str or "带包装" in item_str

            # B. Clean the string for matching (Remove "包装" so "蓝包装20oz" becomes "蓝20oz")
            clean_str = item_str.replace("包装", "").replace("带包装", "")

            # C. Match against map
            matched = False
            # Sort keys by length desc to match longest first (e.g. avoid matching "Slim" inside "Slim Bottle")
            sorted_keys = sorted(name_map.keys(), key=len, reverse=True)

            for key in sorted_keys:
                if key in clean_str:
                    items.append((name_map[key], multiplier, is_pkg))
                    matched = True
                    break

            # Debugging check (Optional)
            # if not matched and "压扁包装" not in item_str:
            #    print(f"Warning: Could not identify product in '{item_str}'")

        # Check for groups (...)
        if '(' in content:
            match = re.search(r'\((.*?)\)', content)
            if match:
                inner = match.group(1)
                sub_items = inner.split('+')
                for sub in sub_items:
                    # Handle inner multiplier if exists (e.g. inside group)
                    sub_mult = 1
                    sub_content = sub
                    if '*' in sub:
                        try:
                            sm, sc = sub.split('*', 1)
                            sub_mult = int(sm)
                            sub_content = sc
                        except:
                            pass

                    final_mult = mult * sub_mult
                    process_single_item(sub_content, final_mult)
        else:
            # Single Item
            process_single_item(content, mult)

    return items

shipped_counts = {}
for ship in shipping_data_raw:
    parsed_items = parse_shipping_details(ship['details'])
    for (p_name, qty, is_packaged) in parsed_items:  # Fixed unpacking
        shipped_counts[p_name] = shipped_counts.get(p_name, 0) + qty

# C. Update 'products_data' with Stock, Signed/Unsigned, and Shipped
for product in products_data:
    p_name = product['name']

    # 1. Update Purchase Stats (Total, Signed, Unsigned)
    if p_name in stock_counts:
        product['total_stock'] = stock_counts[p_name]['total']
        product['us_signed'] = stock_counts[p_name]['signed']
        product['us_unsigned'] = stock_counts[p_name]['unsigned']

    # 2. Update Shipped to China Count
    if p_name in shipped_counts:
        product['shipped_cn'] = shipped_counts[p_name]

# D. Update 'inventory_stats_data' with Stock
# Use the NEW recalculate function to auto-update stats
# ---------------------------------------------------

def format_details(detail_dict):
    if not detail_dict: return "——"
    return ", ".join([f"{name}({qty})" for name, qty in detail_dict.items()])


product_image_lookup = {p['name']: p['image'] for p in products_data}

IMAGE_MAP = {
    "压扁包装": "img/s-l1600.png",
    "礼盒": "img/Stanley 1913 x LoveShackFancy Holiday Quencher ProTour Ornament Set.png",
    "蓝底 20oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® ProTour Flip Straw Tumbler 20 OZ.png",
    "蓝底 30oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® ProTour Flip Straw Tumbler  30 OZ.png",
    "蓝底 40oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® H2.0 FlowState™ Tumbler  40 OZ.png",
    "白底 20oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® ProTour Flip Straw Tumbler 20OZ.png",
    "白底 40oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® H2.0 FlowState™ Tumbler40 oz.png",
    "Slim Bottle": "img/Stanley 1913 x LoveShackFancy Holiday All Day Slim Bottle.png",
    "Holiday Reserve All Day Wine Set": "img/Stanley 1913 x LoveShackFancy Holiday Reserve All Day Wine Set.png",
    "The Reserve Wine Tumbler Set | 11 oz": "img/The Reserve Wine Tumbler Set 11 OZ.png",
    "Everyday Camp Mug Set": "img/Stanley 1913 x LoveShackFancy Holiday Everyday Camp Mug Set.png",
    "Holiday The Quencher Details ProTour Tumbler Set": "img/Holiday The Quencher Details ProTour Tumbler Set  2-pack.png",
    "粉底 40oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® H2.0 FlowState™ Tumbler 40 OZ.png",
    "粉底 30oz": "img/Stanley 1913 x LoveShackFancy Holiday Quencher® H2.0 FlowState™ Tumbler 30 OZ.png",
    "粉底 20oz": "img/ProTour Flip Straw Tumbler oz 20.png",
    "Coquette Bow Chantilly 20oz": "img/ProTour Flip Straw Tumbler 20 OZ.png",
    "情人节款20oz": "img/The Valentine's Day Quencher H2.0 Flowstate Tumbler 20 OZ.png",
    "情人节款30oz": "img/The Valentine's Day Quencher H2.0 Flowstate Tumbler 30 OZ.png",
    "情人节款40oz": "img/The Valentine's Day Quencher H2.0 Flowstate Tumbler 40 OZ.png",
    "情人节款红色20oz": "img/The Valentine's Day Quencher H2.0 Flowstate Tumbler 20 OZ Red.png",
    "情人节款红色30oz": "img/The Valentine's Day Quencher H2.0 Flowstate Tumbler 30 OZ Red.png",
    "情人节款红色40oz": "img/The Valentine's Day Quencher H2.0 Flowstate Tumbler 40 OZ Red.png",

    # Add any other missing products here
}


def recalculate_inventory_stats(shipping_data_raw, current_inventory_stats):
    product_metadata = {}

    # 1. Pre-populate from existing stats template
    for stat in current_inventory_stats:
        product_metadata[stat['产品名称']] = {
            'image': stat.get('image', 'img/default.png'),
            'type': stat.get('类型', 'product'),
            '已发总数': 0, '带包装': 0, '带包装详情': defaultdict(int),
            '不带包装': 0, '不带包装详情': defaultdict(int)
        }

    # 2. Iterate through shipping data
    for ship in shipping_data_raw:
        recipient = ship['recipient']
        parsed_items = parse_shipping_details(ship['details'])

        # REMOVED: Global note logic (as per your previous request)

        for p_name, qty, is_packaged in parsed_items:
            # Init if new (e.g. found in shipping but not in manual stats list)
            if p_name not in product_metadata:
                # FIX: Check products_data first!
                img_path = product_image_lookup.get(p_name)

                # If not in products_data, check IMAGE_MAP
                if not img_path:
                    img_path = IMAGE_MAP.get(p_name, 'img/default.png')

                # Determine type
                p_type = 'product'
                if "礼盒" in p_name:
                    p_type = 'accessory'
                elif "包装" in p_name:
                    p_type = 'packaging'

                product_metadata[p_name] = {
                    'image': img_path,
                    'type': p_type,
                    '已发总数': 0, '带包装': 0, '带包装详情': defaultdict(int),
                    '不带包装': 0, '不带包装详情': defaultdict(int)
                }

            p_data = product_metadata[p_name]
            p_data['已发总数'] += qty

            # --- STRICT PACKAGING LOGIC ---
            final_pack = is_packaged

            # Special Case: "Packaging Only" is implicitly "Packaged"
            if p_name == "压扁包装":
                final_pack = True

            # Assign to correct column
            if final_pack:
                p_data['带包装'] += qty
                p_data['带包装详情'][recipient] += qty
            else:
                p_data['不带包装'] += qty
                p_data['不带包装详情'][recipient] += qty

    final_stats_list = []

    # Sort
    sorted_names = sorted(product_metadata.keys(),
                          key=lambda x: (product_metadata[x]['type'] == 'packaging', -product_metadata[x]['已发总数']))

    for p_name in sorted_names:
        p_data = product_metadata[p_name]

        if p_data['已发总数'] <= 0: continue

        total_stock = 0
        if p_name in stock_counts:
            total_stock = stock_counts[p_name]['total']
        if p_data['type'] == 'packaging': total_stock = 'N/A'

        final_stats_list.append({
            "产品名称": p_name,
            "image": p_data['image'],
            "已发总数": p_data['已发总数'],
            "带包装": p_data['带包装'],
            "带包装详情": format_details(p_data['带包装详情']),
            "不带包装": p_data['不带包装'],
            "不带包装详情": format_details(p_data['不带包装详情']),
            "总库存": total_stock,
            "类型": p_data['type']
        })

    return final_stats_list

# Update the variable
inventory_stats_data = recalculate_inventory_stats(shipping_data_raw, inventory_stats_data)

print("✅ Stock & Shipped counts updated successfully!")

# ==========================================
# 3. MERGE TRACKING INFO INTO PURCHASE ORDERS
# ==========================================
print("🔗 Merging Tracking IDs into Purchase Orders...")


# 1. Helper function to generate tracking URLs
def get_tracking_url(tracking_num):
    if not tracking_num or tracking_num == "——":
        return ""
    tracking_num = tracking_num.strip()
    if tracking_num.upper().startswith("1Z"):
        return f"https://www.ups.com/track?track=yes&trackNums={tracking_num}"
    return f"https://www.fedex.com/fedextrack/?trknbr={tracking_num}"


# 2. Build map
tracking_map = {}
for entry in incoming_orders_data:
    o_id = entry.get('order_id')
    t_num = entry.get('tracking')

    if not o_id or not t_num or t_num == "——": continue

    t_url = entry.get('tracking_url', '')
    if not t_url or t_url == t_num:
        t_url = get_tracking_url(t_num)

    shipment_info = {
        "tracking_number": t_num,
        "tracking_url": t_url,
        "status": entry.get('status', 'Unknown'),
        "carrier": "UPS" if t_num.upper().startswith("1Z") else "FedEx",
        "signed": entry.get('signed', 'No')  # <--- ADD THIS LINE
    }

    if o_id not in tracking_map: tracking_map[o_id] = []

    exists = False
    for s in tracking_map[o_id]:
        if s['tracking_number'] == t_num:
            exists = True
            break
    if not exists: tracking_map[o_id].append(shipment_info)

# 3. Inject
for order in purchase_orders_data:
    o_id = order['order_id']
    if o_id in tracking_map:
        order['shipments'] = tracking_map[o_id]
    else:
        order['shipments'] = []

print("✅ Tracking info merged successfully!")


# ==========================================
# 4. DB INITIALIZATION
# ==========================================

def init_db():
    try:
        client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
        db = client[DB_NAME]
        print("✅ Connected to MongoDB Atlas!")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    print("🔄 Resetting Collections...")
    db.products.drop()
    db.incoming_orders.drop()
    db.customers.drop()
    db.outgoing_shipments.drop()
    db.product_stats.drop()
    db.purchase_orders.drop()

    print("📦 Inserting Data...")
    if products_data: db.products.insert_many(products_data)

    print(f"🚚 Checking Incoming Orders... found {len(incoming_orders_data)} items.")
    if incoming_orders_data: db.incoming_orders.insert_many(incoming_orders_data)

    if inventory_stats_data: db.product_stats.insert_many(inventory_stats_data)
    if purchase_orders_data: db.purchase_orders.insert_many(purchase_orders_data)

    print("✈️ Processing Customers and Shipments...")
    customers_map = {}
    seen_tracking_numbers = set()

    for item in shipping_data_raw:
        tracking_num = item['tracking_number']

        # 1. Skip Duplicate Shipments
        if tracking_num in seen_tracking_numbers:
            print(f"⚠️ Skipping duplicate tracking number: {tracking_num}")
            continue
        seen_tracking_numbers.add(tracking_num)

        # 2. CLEAN DATA (Crucial Step)
        # Convert to string and strip whitespace to prevent "Alice" and "Alice " being two people
        raw_phone = str(item['phone']).strip()
        raw_name = str(item['recipient']).strip()

        # 3. CUSTOMER IDENTIFICATION (Phone + Name)
        # Using both ensures family members sharing a phone get separate profiles
        customer_key = (raw_phone, raw_name)

        customer_data = {
            "name": raw_name,
            "phone": raw_phone,
            "address": item['address']  # This stores the LATEST address in the customer profile
        }

        # Check if this specific person (Phone + Name) exists
        if customer_key not in customers_map:
            existing_customer = db.customers.find_one({
                "phone": raw_phone,
                "name": raw_name
            })

            if existing_customer:
                customer_id = existing_customer['_id']
                # Update address to the most recent one used
                db.customers.update_one({"_id": customer_id}, {"$set": {"address": item['address']}})
            else:
                res = db.customers.insert_one(customer_data)
                customer_id = res.inserted_id

            customers_map[customer_key] = customer_id
        else:
            customer_id = customers_map[customer_key]

        # 4. CREATE SHIPMENT
        # We allow the shipment to store its own snapshot of the address
        shipment_data = {
            "tracking_number": tracking_num,
            "tracking_url": f"https://www.junanex.com/tracking?code={tracking_num}&mobile={raw_phone}",
            "customer_id": customer_id,
            "recipient": raw_name,
            "details": item['details'],
            "weight": item['weight'],
            "fee": item.get('fee', 0),
            "status": item['status'],
            "date": item.get('date', ''),
            "carrier": "JunAn Express",
            "address": item['address'],  # Store specific address for this shipment history
            "note": item.get('note', '')
        }
        db.outgoing_shipments.insert_one(shipment_data)

    # --- SUMMARY ---
    print("\n✅ Database Reset Complete!")
    print(f"   - Products: {db.products.count_documents({})}")
    print(f"   - Stats: {db.product_stats.count_documents({})}")
    print(f"   - Purchase Orders: {db.purchase_orders.count_documents({})}")
    print(f"   - Incoming Orders: {db.incoming_orders.count_documents({})}")
    print(f"   - Outgoing Shipments: {db.outgoing_shipments.count_documents({})}")


if __name__ == "__main__":
    init_db()