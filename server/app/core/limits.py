import math
import threading
import time
from collections import deque

from app.core.errors import ApiError


class RateLimiter:
    def __init__(self):
        self.events = {}
        self.lock = threading.Lock()

    def check(self, *limits):
        now = time.monotonic()
        with self.lock:
            for key in list(self.events):
                queue, window = self.events[key]
                while queue and queue[0] <= now - window:
                    queue.popleft()
                if not queue:
                    del self.events[key]
            for key, count, window in limits:
                queue, _ = self.events.setdefault(key, (deque(), window))
                if len(queue) >= count:
                    delay = max(1, math.ceil(window - (now - queue[0])))
                    raise ApiError(429, "RATE_LIMITED", "Слишком много запросов", details={"retry_after": delay})
            for key, _, _ in limits:
                self.events[key][0].append(now)


# лимиты одного процесса
limiter = RateLimiter()
