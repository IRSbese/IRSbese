"""Простой нагрузочный smoke-test для запущенного IRSbese.
Пример: python artifacts/qa/load_test.py https://irsbese.example 20 100
"""
import sys
import time
import threading
import urllib.request
from statistics import mean

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000/'
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 10
REQUESTS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
results = []
lock = threading.Lock()

def worker(count):
    local = []
    for _ in range(count):
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(URL, timeout=15) as response:
                response.read(1024)
                local.append((response.status, time.perf_counter() - started))
        except Exception:
            local.append((0, time.perf_counter() - started))
    with lock:
        results.extend(local)

start = time.perf_counter()
threads = [threading.Thread(target=worker, args=(REQUESTS // WORKERS + (1 if i < REQUESTS % WORKERS else 0),)) for i in range(WORKERS)]
for thread in threads: thread.start()
for thread in threads: thread.join()
elapsed = time.perf_counter() - start
ok = [duration for status, duration in results if 200 <= status < 400]
failed = len(results) - len(ok)
print(f'URL: {URL}')
print(f'Requests: {len(results)} | workers: {WORKERS} | total: {elapsed:.2f}s')
print(f'OK: {len(ok)} | failed: {failed} | RPS: {len(results)/elapsed:.2f}')
if ok:
    print(f'Mean latency: {mean(ok)*1000:.1f} ms | max: {max(ok)*1000:.1f} ms')
print('This is a basic smoke test, not a capacity certification.')
