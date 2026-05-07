import logging
from fastapi import FastAPI, Request, HTTPException
from starlette.responses import Response
from datetime import datetime, timezone
from database import get_connection
from models import unix_ms_to_dt, parse_order_relay, parse_order_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ETL Webhook")

@app.get("/ping")
def ping():
    return {"ping": "pong"}

# Health check
@app.get("/", methods=["GET", "HEAD"])
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Order relay
@app.post("/webhook/order-relay")
async def order_relay(request: Request):
    try:
        data = await request.json()
        logger.info(f"Order relay received: {data.get('order', {}).get('details', {}).get('id')}")

        order = parse_order_relay(data)

        if not order["up_order_id"]:
            return HTTPException("status_code=400", detail="Mising order Id")
        
        sql = """
            INSERT INTO up_orders(
                up_order_id, biz_id, biz_name,
                store_id, store_name, store_city,
                customer_id, customer_phone, channel,
                order_placed_at, promised_delivery_at,
                payable_amount, order_subtotal, current_state
            ) VALUES (
                %(up_order_id)s, %(biz_id)s, %(biz_name)s,
                %(store_id)s, %(store_name)s, %(store_city)s,
                %(customer_id)s, %(customer_phone)s, %(channel)s,
                %(order_placed_at)s, %(promised_delivery_at)s,
                %(payable_amount)s, %(order_subtotal)s, %(current_state)s
            )
            ON CONFLICT (up_order_id) DO UPDATE SET
                current_state = EXCLUDED.current_state,
                promised_delivery_at = EXCLUDE.promised_delivery_at,
                payable_amount = EXCLUDE.payable_amount,
                fetched_at = NOW()
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, order)
            conn.commit()

            logger.info(f"Order {order['up_order_id']} upserted successfully")
            return {"status":"ok", "order_id": order["up_order_id"]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order relay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

# Order status update
@app.post('/webhook/order-status')
async def order_status(request:Request):
    try:
        data = await request.json()
        logger.info(f"status update recieved: order {data.get('order_id')} → {data.get('new_state')}")

        event = parse_order_status(data)

        if not event["up_order_id"]:
            raise HTTPException(status_code=400, detail="missing order id")
        
        with get_connection() as conn:
            with conn.cursor as cur:

                cur.execute("""
                     INSERT INTO up_order_events(
                        up_order_id, store_id, prev_state,
                        new_state, event_at, updated_by  
                    ) VALUES (
                        %(up_order_id)s, %(store_id)s, %(prev_state)s,
                        %(new_state)s, %(event_at)s, %(updated_by)s      
                    )
                    ON_CONFLICT (up_order_id, new_state) DO NOTHING
                )""", event)

                cur.execute("""
                    UPDATE up_orders
                    SET current_state = %(new_state)s,
                        fetched_at    = NOW()
                    WHERE up_order_id = %(up_order_id)s
                """, event)
        conn.commit()

        logger.info(f"Event recorded: order {event['up_order_id']} → {event['new_state']}")
        return {"status": "ok", "order_id": event["up_order_id"], "new_state": event["new_state"]}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 
