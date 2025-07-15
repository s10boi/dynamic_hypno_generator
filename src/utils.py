import time


def wait_until_next_second():
    """Block until the next exact second of real time."""
    now = time.time()
    sleep_time = 1 - (now % 1)
    time.sleep(sleep_time)
