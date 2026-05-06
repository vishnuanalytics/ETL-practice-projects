from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import io
import csv

app = FastAPI()

# --- 1. Models ---

class BillSummary(BaseModel):
    total_amount: float = 0.0
    merchant_total: float = 0.0
    sub_total_amount: float = 0.0
    total_discount: float = 0.0
    merchant_discount: float = 0.0
    agg_discount: float = 0.0
    total_tax: float = 0.0
    merchant_tax: float = 0.0
    agg_tax: float = 0.0
    charges: float = 0.0

class OrderDetails(BaseModel):
    order_id: int
    platform_id: str
    channel: str
    order_bill_summary: BillSummary

class StoreResponse(BaseModel):
    store_name: str
    store_id: int
    store_ref_id: Optional[str]
    city: str
    orders: List[OrderDetails]

# --- 2. In-Memory Storage ---

# Key: store_id (int), Value: StoreResponse object
db_storage: Dict[int, StoreResponse] = {}

# --- 3. Helpers ---

def to_type(val, func):
    try:
        return func(val) if val else func(0)
    except:
        return func(0)

def normalize_row(row):
    return {k.strip().lower().replace(" ", "_"): v.strip() if v else None for k, v in row.items()}

# --- 4. Logic to reduce repetitive mapping ---

def map_to_nested(clean: dict) -> OrderDetails:
    """Automates the creation of nested models from the flat clean dict"""
    bill = BillSummary(
        total_amount=clean.get("total_amount", 0),
        merchant_total=clean.get("merchant_total", 0),
        sub_total_amount=clean.get("sub_total_amount", 0),
        total_discount=clean.get("discount", 0),
        merchant_discount=clean.get("merchant_discount", 0),
        agg_discount=clean.get("aggregator_discount", 0),
        total_tax=clean.get("total_taxes", 0),
        merchant_tax=clean.get("merchant_taxes", 0),
        agg_tax=clean.get("aggregator_taxes", 0),
        charges=clean.get("charges", 0)
    )
    return OrderDetails(
        order_id=clean.get("order_id"),
        platform_id=clean.get("external_platform_id") or "N/A",
        channel=clean.get("channel") or "N/A",
        order_bill_summary=bill
    )

# --- 5. Routes ---

@app.post('/upload_file')
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    
    cleaned_flat_list = []
    
    for row in reader:
        norm = normalize_row(row)
        
        # Quick type conversion
        s_id = to_type(norm.get("store_id"), int)
        
        # Build the flat clean dictionary for the 'cleaned context'
        # This reduces writing manual assignments for every column
        clean_entry = {k: (to_type(v, float) if 'amount' in k or 'tax' in k or 'discount' in k else v) 
                       for k, v in norm.items()}
        clean_entry["order_id"] = to_type(norm.get("order_id"), int)
        clean_entry["store_id"] = s_id
        
        cleaned_flat_list.append(clean_entry)

        # Update In-Memory Store grouping
        if s_id not in db_storage:
            db_storage[s_id] = StoreResponse(
                store_name=norm.get("store_name", "Unknown"),
                store_id=s_id,
                store_ref_id=norm.get("store_ref_id"),
                city=norm.get("city", "Unknown"),
                orders=[]
            )
        
        # Convert flat clean entry to nested OrderDetails
        db_storage[s_id].orders.append(map_to_nested(clean_entry))

    return {
        "status": "Success",
        "total_processed": len(cleaned_flat_list),
        "flat_data": cleaned_flat_list
    }

@app.get('/stores', response_model=List[StoreResponse])
async def get_all_stores():
    """Returns all stores and their nested orders"""
    return list(db_storage.values())

@app.get('/stores/{store_id}', response_model=StoreResponse)
async def get_store_by_id(store_id: int):
    """Returns orders for a specific store"""
    store = db_storage.get(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store