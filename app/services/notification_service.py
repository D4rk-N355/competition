def send_push_notification(target, message):
	"""
	發送推播通知（範例：僅列印訊息）
	"""
	print(f"推播給 {target}：{message}")

def send_email(recipient, subject, body):
	"""
	發送 Email 通知（範例：僅列印訊息）
	"""
	print(f"Email 給 {recipient}，主旨：{subject}，內容：{body}")

def send_sms(phone_number, message):
	"""
	發送簡訊通知（範例：僅列印訊息）
	"""
	print(f"簡訊給 {phone_number}：{message}")

def notify_payment_system(order_id, data):
    """通知支付系統（範例：用推播或 API 呼叫）"""
    message = f"訂單 {order_id} 已建立，金額計算中，內容：{data}"
    send_push_notification("支付系統", message)

def notify_restaurant(order_id, data):
    """通知餐廳（範例：用 Email 或簡訊）"""
    subject = f"新訂單通知 #{order_id}"
    body = f"餐廳收到新訂單：{data}"
    send_email("restaurant@example.com", subject, body)
    send_sms("0912345678", body)
