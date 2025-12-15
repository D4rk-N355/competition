import app.services.order_service as order_service
test_order = {
    "restaurant_id": 2,
    "table_id": "T05",
    "items": [
        {"dish_id": 1, "name": "雞肉飯", "quantity": 2, "price": 80},
        {"dish_id": 4, "name": "滷肉飯", "quantity": 1, "price": 60}
    ],
    "note": "不要辣",
    "payment_method": "credit_card"
}

order_id = order_service.save_order_to_db(test_order)
print("建立訂單 ID:", order_id)