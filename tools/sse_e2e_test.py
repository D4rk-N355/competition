"""簡易 E2E 測試：
1. 建立一筆訂單（POST /api/order）
2. 開啟 SSE 訂閱 /api/notifications/stream/<restaurant_id>
3. 更新訂單狀態（PUT /api/order/<order_id>/status），檢查是否收到 SSE event
"""
import requests
import threading
import time
import json

BASE = "http://127.0.0.1:2323/api"

def sse_listen(restaurant_id, stop_event):
    url = f"{BASE}/notifications/stream/{restaurant_id}"
    print(f"連線 SSE: {url}")
    with requests.get(url, stream=True) as r:
        if r.status_code != 200:
            print("SSE 連線失敗，狀態碼：", r.status_code, r.text)
            return
        for line in r.iter_lines(decode_unicode=True):
            if stop_event.is_set():
                break
            if not line:
                continue
            # SSE lines可能以 'data: ' 或 'event: '
            try:
                if line.startswith('data:'):
                    payload = line[len('data:'):].strip()
                    # 嘗試解析 JSON
                    try:
                        obj = json.loads(payload)
                    except Exception:
                        obj = payload
                    print("SSE data:", obj)
                    # 停在收到 order_update
                    if isinstance(obj, dict) and obj.get('type') == 'order_status_updated':
                        stop_event.set()
                        break
                else:
                    print("SSE line:", line)
            except Exception as e:
                print('解析 SSE 發生錯誤', e)

def main():
    restaurant_id = 'R002'
    # 建立訂單
    body = {
        "restaurant_id": restaurant_id,
        "items": [
            {"dish_id": "D1", "name": "Test Dish", "price": 100, "quantity": 1}
        ],
        "note": "測試用",
    }
    print('建立訂單...')
    r = requests.post(f"{BASE}/order", json=body)
    print('POST /order ->', r.status_code, r.text)
    if r.status_code != 201:
        print('建立訂單失敗，終止測試')
        return
    order = r.json()
    order_id = order.get('order_id') or order.get('order_id')
    if not order_id:
        # 可能回傳整個 order 物件
        order_id = order.get('order_id') if isinstance(order, dict) else None
    print('order_id=', order_id)

    stop_event = threading.Event()
    t = threading.Thread(target=sse_listen, args=(restaurant_id, stop_event), daemon=True)
    t.start()

    # 等待 SSE 連線建立
    time.sleep(1.5)

    print('更新訂單狀態為 accepted...')
    update = {"status": "accepted"}
    r2 = requests.put(f"{BASE}/order/{order_id}/status", json=update)
    print('PUT status ->', r2.status_code, r2.text)

    # 等待 SSE 收到訊息或 timeout
    timeout = 10
    waited = 0
    while not stop_event.is_set() and waited < timeout:
        time.sleep(0.5)
        waited += 0.5

    if stop_event.is_set():
        print('已收到 SSE order_update event')
    else:
        print('未在時間內收到 SSE 訊息')

if __name__ == '__main__':
    main()
