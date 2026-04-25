"""
Generate sample retail dataset for DataSoul demo
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)

rows = 5000

# ─── Generate data ───
order_ids = range(1001, 1001 + rows)
customer_ids = [f"CUST-{random.randint(1000, 5000)}" for _ in range(rows)]
products = ["Laptop", "Mouse", "Keyboard", "Monitor", "Headphones", "USB Hub",
            "Webcam", "Speaker", "Charger", "Phone Case", "Tablet", "SSD",
            "RAM Stick", "Power Bank", "Cable Pack"]
categories = ["Electronics", "Accessories", "Peripherals", "Audio", "Storage"]
regions = ["East", "West", "South", "North", "Central"]
payment_methods = ["Credit Card", "UPI", "Debit Card", "Cash on Delivery"]
statuses = ["Delivered", "Shipped", "Processing"]

dates = [datetime(2023, 1, 1) + timedelta(days=random.randint(0, 545)) for _ in range(rows)]

data = {
    "order_id": list(order_ids),
    "customer_id": customer_ids,
    "product_name": [random.choice(products) for _ in range(rows)],
    "category": [random.choice(categories) for _ in range(rows)],
    "quantity": [random.randint(1, 10) for _ in range(rows)],
    "unit_price": [round(random.uniform(200, 45000), 2) for _ in range(rows)],
    "order_date": dates,
    "region": [random.choice(regions) for _ in range(rows)],
    "payment_method": [random.choice(payment_methods) for _ in range(rows)],
    "status": [random.choice(statuses) for _ in range(rows)],
}

df = pd.DataFrame(data)

# Add derived column
df["total_amount"] = df["quantity"] * df["unit_price"]

# Add discount (with high missing rate)
df["discount"] = np.random.uniform(0, 30, rows)
df.loc[df.sample(frac=0.25, random_state=42).index, "discount"] = np.nan

# ─── Inject data quality issues ───

# Missing customer_ids (3%)
df.loc[df.sample(frac=0.03, random_state=10).index, "customer_id"] = np.nan

# Missing regions (8%)
df.loc[df.sample(frac=0.08, random_state=20).index, "region"] = np.nan

# Case inconsistencies
inconsistent_map = {
    "East": ["East", "east", "EAST", "East "],
    "West": ["West", "west", "WEST"],
    "South": ["South", "south"],
    "North": ["North", "north", "NORTH"],
    "Central": ["Central", "central"],
}
for i in range(len(df)):
    if pd.notna(df.loc[i, "region"]):
        original = df.loc[i, "region"]
        if original in inconsistent_map:
            df.loc[i, "region"] = random.choice(inconsistent_map[original])

# Duplicate rows (1%)
dup_indices = df.sample(n=50, random_state=30).index
duplicates = df.loc[dup_indices].copy()
df = pd.concat([df, duplicates], ignore_index=True)

# Outlier prices
for _ in range(15):
    idx = random.randint(0, len(df) - 1)
    df.loc[idx, "unit_price"] = random.uniform(80000, 200000)
    df.loc[idx, "total_amount"] = df.loc[idx, "quantity"] * df.loc[idx, "unit_price"]

# Mixed date formats (some DD/MM, some MM/DD)
date_strs = []
for d in df["order_date"]:
    if random.random() < 0.15:
        date_strs.append(d.strftime("%d/%m/%Y"))
    elif random.random() < 0.3:
        date_strs.append(d.strftime("%m-%d-%Y"))
    else:
        date_strs.append(d.strftime("%Y-%m-%d"))
df["order_date"] = date_strs

# Save
output_path = "sample_datasets/retail_sales_demo.csv"
import os
os.makedirs("sample_datasets", exist_ok=True)
df.to_csv(output_path, index=False)
print(f"✅ Generated {len(df)} rows → {output_path}")
print(f"   Missing customer_id: {df['customer_id'].isna().sum()}")
print(f"   Missing region: {df['region'].isna().sum()}")
print(f"   Missing discount: {df['discount'].isna().sum()}")
print(f"   Duplicates: {df.duplicated().sum()}")
print(f"   Unique regions: {df['region'].dropna().nunique()} (should be >5 due to case issues)")
