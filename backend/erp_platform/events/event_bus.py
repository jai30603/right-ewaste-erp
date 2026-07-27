"""
Enterprise Event Bus
Decoupled publish/subscribe system for inter-module communication.
Modules publish events; subscribers react without tight coupling.
"""
import json
import threading
import logging
from datetime import datetime
from typing import Callable, Dict, List, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ErpEvent:
    event_type: str
    source_module: str
    payload: Dict[str, Any] = field(default_factory=dict)
    user_name: str = "System"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    event_id: str = field(default_factory=lambda: __import__('uuid').uuid4().hex)

    def to_dict(self):
        return asdict(self)


class EventBus:
    """
    Thread-safe in-process event bus.
    Supports synchronous (in-request) and async (background thread) delivery.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler for a specific event type. Use '*' for all events."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
            logger.debug(f"[EventBus] {handler.__name__} subscribed to '{event_type}'")

    def publish(self, event: ErpEvent, async_mode: bool = False):
        """Publish an event to all matching subscribers, then persist to DB."""
        if async_mode:
            thread = threading.Thread(target=self._dispatch, args=(event,), daemon=True)
            thread.start()
        else:
            self._dispatch(event)
        # Always persist to DB
        self._persist(event)

    def _dispatch(self, event: ErpEvent):
        with self._lock:
            handlers = list(self._subscribers.get(event.event_type, []))
            wildcard = list(self._subscribers.get('*', []))
        all_handlers = handlers + wildcard
        for handler in all_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"[EventBus] Handler {handler.__name__} failed for {event.event_type}: {e}")

    def _persist(self, event: ErpEvent):
        """Persist event to platform_event_log table."""
        try:
            from database import get_connection
            conn = get_connection()
            conn.execute(
                "INSERT INTO platform_event_log (event_type, source_module, payload) VALUES (?, ?, ?)",
                (event.event_type, event.source_module, json.dumps(event.payload))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[EventBus] Failed to persist event {event.event_type}: {e}")

    def get_handlers(self) -> Dict[str, List[str]]:
        """Return registered handlers (for admin introspection)."""
        with self._lock:
            return {k: [h.__name__ for h in v] for k, v in self._subscribers.items()}


# Singleton instance
event_bus = EventBus()
