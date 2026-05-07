from datetime import datetime, timezone
from typing import Optional

def unix_ms_to_dt(ms)->Optional[datetime]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc)

def parse_order_relay(data:dict)->dict:
    order = data.get("order", {})
    details = order.get("details", {})
    store    = order.get("store", {})
    customer = data.get("customer", {})

    return {
        "up_order_id": details.get("id"),
        "biz_id": details.get("biz_id"),
        "biz_name": details.get("biz_name"),
        "store_id": store.get("id"),
        "store_name": store.get("name"),
        "store_city": store.get("city"),
        "customer_id": customer.get("id"),
        "customer_phone": customer.get("phone"),
        "channel": customer.get("channel"),
        "order_placed_at": unix_ms_to_dt(details.get("created")),
        "promised_delivery_at": unix_ms_to_dt(details.get("delivery_datetime")),
        "payable_amount": details.get("payable_amount"),
        "order_subtotal": details.get("order_subtotal"),
        "current_state": details.get("state")
    }

def parse_order_status(data:dict)->dict:
    return {
        "up_order_id": data.get("order_id"),
        "store_id": data.get("store_upipr_id"),
        "prev_state": data.get("prev_state"),
        "new_state": data.get("new_state"),
        "event_at": unix_ms_to_dt(data.get("timestamp_unix")),
        "updated_by": data.get("updater", {}).get("name")
    }