from flask import Blueprint, jsonify, request, Response, stream_with_context
from app.services.order_service import (
    save_order_to_db,
    get_order_by_id,
    update_order_status_in_db,
    notify_payment_system,
    notify_restaurant
)
from app.services import realtime_service

order_bp = Blueprint("order", __name__, url_prefix="/api")

def not_found(msg="訂單不存在"):
    return jsonify({"error": msg}), 404

@order_bp.route("/order", methods=["POST"])
def create_order():
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少訂單資料"}), 400

    order_id = save_order_to_db(data)
    notify_payment_system(order_id, data)
    notify_restaurant(order_id, data)

    response = get_order_by_id(order_id)
    # publish SSE: 通知餐廳有新訂單（order created）
    try:
        restaurant_id = response.get("restaurant_id") if response else data.get("restaurant_id")
        realtime_service.publish(restaurant_id, {"type": "order_created", "order": response, "message": "訂單已送出"}, event="order_created")
    except Exception:
        pass

    # 在回傳中加入提示訊息，前端可直接顯示
    resp = response.copy() if isinstance(response, dict) else {"order": response}
    resp["message"] = "訂單已送出"
    return jsonify(resp), 201

@order_bp.route("/order/<int:order_id>", methods=["GET"])
def get_order(order_id):
    order = get_order_by_id(order_id)
    return jsonify(order) if order else not_found()

@order_bp.route("/order/<int:order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "缺少狀態"}), 400

    updated = update_order_status_in_db(order_id, new_status)
    if updated:
        order = get_order_by_id(order_id)  # 回傳完整 JSON
        return jsonify(order), 200
    return not_found()


@order_bp.route('/notifications/stream/<restaurant_id>')
def notifications_stream(restaurant_id):
    """SSE endpoint: 前端可連到此路徑接收餐廳的即時通知"""
    def generator():
        yield from realtime_service.subscribe(restaurant_id)

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/event-stream',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    }
    return Response(stream_with_context(generator()), headers=headers)

@order_bp.route("/order/<int:order_id>", methods=["DELETE"])
def cancel_order(order_id):
    cancelled = update_order_status_in_db(order_id, "cancelled")
    if cancelled:
        order = get_order_by_id(order_id)  # 回傳完整 JSON
        return jsonify(order), 200
    return not_found()