"""Per-instance FIFO stage limits; never hold a BERT slot while waiting for an LLM."""

import threading
import time
from collections import deque
from contextlib import contextmanager


class AnalysisBusy(Exception):
    pass


class StageLimit:
    def __init__(self, capacity):
        self.capacity = capacity
        self.active = 0
        self.waiters = deque()
        self.condition = threading.Condition()

    @contextmanager
    def acquire(self, deadline):
        ticket = object()
        with self.condition:
            self.waiters.append(ticket)
            try:
                while self.waiters[0] is not ticket or self.active >= self.capacity:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AnalysisBusy()
                    self.condition.wait(remaining)
                self.waiters.popleft()
                self.active += 1
                self.condition.notify_all()
            except BaseException:
                self.waiters.remove(ticket)
                self.condition.notify_all()
                raise
        try:
            yield
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()
