import requests

BASE_URL = "http://127.0.0.1:2323/api"

def print_response(label, response):
    """統一印出狀態碼與回傳內容"""
    print(f"{label} 狀態碼:", response.status_code)
    try:
        print(f"{label} 回傳 JSON:", response.json())
    except Exception:
        print(f"{label} 回傳內容不是 JSON:", response.text)

def test_create_order():
    payload = {
        "restaurant_id": 1,
        "table_id": "T05",
        "items": [
            {"dish_id": 1, "name": "Spaghetti", "quantity": 1, "price": 220}
        ],
        "note": "不要辣",
        "payment_method": "credit_card"
    }
    response = requests.post(f"{BASE_URL}/order", json=payload)
    print_response("建立訂單", response)
    return response.json().get("order_id")  # 直接取出 order_id

def test_get_order(order_id):
    response = requests.get(f"{BASE_URL}/order/{order_id}")
    print_response("查詢訂單", response)

def test_update_order(order_id):
    payload = {"status": "paid"}
    response = requests.put(f"{BASE_URL}/order/{order_id}/status", json=payload)
    print_response("更新狀態", response)

def test_cancel_order(order_id):
    response = requests.delete(f"{BASE_URL}/order/{order_id}")
    print_response("取消訂單", response)

if __name__ == "__main__":
    # 1. 建立訂單，取得 order_id
    order_id = test_create_order()

    # 2. 用建立的 order_id 測試查詢、更新、取消
    test_get_order(order_id)
    test_update_order(order_id)
    test_cancel_order(order_id)