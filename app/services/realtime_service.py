import json
import queue
import threading
import time
from typing import Dict, List


_subscribers: Dict[str, List[queue.Queue]] = {}
_lock = threading.Lock()

def _format_sse(data: dict, event: str = None) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    s = ""
    if event:
        s += f"event: {event}\n"
    for line in payload.splitlines():
        s += f"data: {line}\n"
    s += "\n"
    return s

def subscribe(restaurant_id: str):
    """
    Generator for SSE streaming. Yields SSE-formatted strings.
    """
    q = queue.Queue()
    with _lock:
        _subscribers.setdefault(str(restaurant_id), []).append(q)

    try:
        # initial ping
        yield _format_sse({"type": "connected", "restaurant_id": restaurant_id})
        while True:
            try:
                msg = q.get(timeout=15)  # timeout to allow client reconnect checks
                yield _format_sse(msg.get("data", {}), event=msg.get("event"))
            except queue.Empty:
                # keep alive comment to prevent proxies from closing
                yield ": keep-alive\n\n"
    finally:
        # remove subscriber on disconnect
        with _lock:
            lst = _subscribers.get(str(restaurant_id), [])
            if q in lst:
                lst.remove(q)

def publish(restaurant_id: str, data: dict, event: str = None):
    """
    Publish an event to all subscribers for the given restaurant_id.
    """
    with _lock:
        lst = list(_subscribers.get(str(restaurant_id), []))
    payload = {"event": event, "data": data}
    for q in lst:
        try:
            q.put_nowait(payload)
        except Exception:
            # on full or closed queue, ignore; subscriber cleanup happens on disconnect
            pass

def broadcast_all(data: dict, event: str = None):
    """
    Broadcast to all subscribers across restaurants.
    """
    with _lock:
        all_queues = [q for lst in _subscribers.values() for q in lst]
    payload = {"event": event, "data": data}
    for q in all_queues:
        try:
            q.put_nowait(payload)
        except Exception:
            pass
