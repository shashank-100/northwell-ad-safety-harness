"""Infrastructure retries (timeouts, CLI errors). Separate from content revision attempts (invariant 6)."""
import time


class InfraError(Exception):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category  # TIMEOUT | WRITER_FAILURE | REVIEWER_FAILURE


def with_retries(fn, *, attempts=3, backoff_s=2.0, retry_on=("TIMEOUT", "WRITER_FAILURE", "REVIEWER_FAILURE")):
    for i in range(attempts):
        try:
            return fn()
        except InfraError as e:
            if e.category not in retry_on or i == attempts - 1:
                raise
            time.sleep(backoff_s * (i + 1))
