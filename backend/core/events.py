import asyncio
import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        logger.info(f"Subscribed callback to event: {event_name}")

    async def emit(self, event_name: str, *args, **kwargs):
        if event_name not in self._listeners:
            return
        logger.info(f"Emitting event: {event_name}")
        for callback in self._listeners[event_name]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in event listener for {event_name}: {e}")

event_bus = EventBus()
