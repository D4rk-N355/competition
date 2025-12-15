from sqlalchemy import create_engine, MetaData, Table, insert, select, update
from sqlalchemy.orm import Session
from datetime import datetime
import os
import sqlalchemy

# 支援環境變數覆寫，且在無法連線時退回到 in-memory 模式以便本地開發/測試
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'DATABASE_URL',
    "mysql+pymysql://root:@0.tcp.jp.ngrok.io:17180/e-system-delivery?charset=utf8mb4"
)

engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=False)
metadata = MetaData()

# 嘗試自動載入資料表，若無法連線則退回 in-memory 實作
orders_table = None
order_items_table = None
_inmem_orders = {}
_inmem_items = {}
_inmem_next_id = 1

try:
    orders_table = Table('orders', metadata, autoload_with=engine)
    order_items_table = Table('order_items', metadata, autoload_with=engine)
except Exception:
    # 無法連線或表不存在，使用 in-memory fallback
    orders_table = None
    order_items_table = None

# 為了觸發通知與即時推播，匯入相關 service（延後匯入以避免循環匯入問題）
from app.services import realtime_service, notification_service

def calculate_total(data):
    """計算訂單總金額"""
    total = 0
    for item in data.get('items', []):
        total += item.get('price', 0) * item.get('quantity', 1)
    return total

def save_order_to_db(data):
    """儲存訂單資料到資料庫，回傳訂單編號"""
    global _inmem_next_id
    # 若有實際資料庫表則使用 DB 寫入
    if orders_table is not None and order_items_table is not None:
        with Session(engine) as session:
            try:
                # 建立訂單主表
                stmt = insert(orders_table).values(
                    restaurant_id=data["restaurant_id"],
                    table_id=data.get("table_id"),
                    note=data.get("note", ""),
                    status="pending",
                    total_amount=calculate_total(data),
                    payment_method=data.get("payment_method", "credit_card"),
                    payment_status="unpaid",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                result = session.execute(stmt)
                order_id = result.inserted_primary_key[0]

                # 建立訂單明細
                for item in data.get("items", []):
                    item_stmt = insert(order_items_table).values(
                        order_id=order_id,
                        dish_id=item["dish_id"],
                        name=item.get("name"),
                        quantity=item.get("quantity", 1),
                        price=item.get("price", 0)
                    )
                    session.execute(item_stmt)

                session.commit()
                return order_id
            except Exception as e:
                session.rollback()
                raise e

    # in-memory fallback
    order_id = _inmem_next_id
    _inmem_next_id += 1
    now = datetime.now().isoformat()
    _inmem_orders[order_id] = {
        "order_id": order_id,
        "restaurant_id": data.get("restaurant_id"),
        "table_id": data.get("table_id"),
        "note": data.get("note", ""),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "total_amount": float(calculate_total(data)),
        "payment": {"method": data.get("payment_method", "credit_card"), "status": "unpaid"},
    }
    _inmem_items[order_id] = [
        {"dish_id": item.get("dish_id"), "name": item.get("name"), "quantity": item.get("quantity", 1), "price": float(item.get("price", 0))}
        for item in data.get("items", [])
    ]
    return order_id

def get_order_by_id(order_id):
    """查詢訂單主表與明細"""
    if orders_table is not None and order_items_table is not None:
        with engine.connect() as conn:
            stmt = select(orders_table).where(orders_table.c.order_id == order_id)
            order = conn.execute(stmt).mappings().first()
            if not order:
                return None

            item_stmt = select(order_items_table).where(order_items_table.c.order_id == order_id)
            items = conn.execute(item_stmt).mappings().all()

            return {
                "order_id": order["order_id"],
                "restaurant_id": order["restaurant_id"],
                "table_id": order["table_id"],
                "note": order["note"],
                "status": order["status"],
                "created_at": order["created_at"].isoformat(),
                "updated_at": order["updated_at"].isoformat(),
                "total_amount": float(order["total_amount"]),
                "payment": {
                    "method": order["payment_method"],
                    "status": order["payment_status"]
                },
                "items": [
                    {
                        "dish_id": item["dish_id"],
                        "name": item["name"],
                        "quantity": item["quantity"],
                        "price": float(item["price"])
                    }
                    for item in items
                ]
            }

    # in-memory fallback
    o = _inmem_orders.get(order_id)
    if not o:
        return None
    return {
        "order_id": o["order_id"],
        "restaurant_id": o["restaurant_id"],
        "table_id": o.get("table_id"),
        "note": o.get("note"),
        "status": o.get("status"),
        "created_at": o.get("created_at"),
        "updated_at": o.get("updated_at"),
        "total_amount": o.get("total_amount"),
        "payment": o.get("payment"),
        "items": _inmem_items.get(order_id, [])
    }

def update_order_status_in_db(order_id, new_status):
    """更新訂單狀態"""
    if orders_table is not None:
        with Session(engine) as session:
            try:
                stmt = update(orders_table).where(
                    orders_table.c.order_id == order_id
                ).values(
                    status=new_status,
                    updated_at=datetime.now()
                )
                result = session.execute(stmt)
                session.commit()
                updated = result.rowcount > 0
                if updated:
                    try:
                        order = get_order_by_id(order_id)
                        # publish SSE event to restaurant
                        restaurant_id = order.get('restaurant_id') if order else None
                        if restaurant_id:
                            realtime_service.publish(restaurant_id, {"type": "order_status_updated", "order": order}, event="order_update")
                        # call central notification service
                        try:
                            notification_service.notify_restaurant(order_id, order)
                        except Exception:
                            pass
                    except Exception:
                        pass
                return updated
            except Exception as e:
                session.rollback()
                raise e

    # in-memory fallback
    o = _inmem_orders.get(order_id)
    if not o:
        return False
    o["status"] = new_status
    o["updated_at"] = datetime.now().isoformat()
    # publish and notify for in-memory
    try:
        order = get_order_by_id(order_id)
        restaurant_id = order.get('restaurant_id') if order else None
        if restaurant_id:
            realtime_service.publish(restaurant_id, {"type": "order_status_updated", "order": order}, event="order_update")
        try:
            notification_service.notify_restaurant(order_id, order)
        except Exception:
            pass
    except Exception:
        pass
    return True

def cancel_order_in_db(order_id):
    """取消訂單"""
    return update_order_status_in_db(order_id, "cancelled")

def notify_payment_system(order_id, data):
    """模擬通知支付系統"""
    print(f"通知支付系統：訂單 {order_id} 金額 {calculate_total(data)}")

def notify_restaurant(order_id, data):
    """模擬通知餐廳"""
    print(f"通知商家：新訂單 {order_id}，請準備餐點")