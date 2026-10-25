"""Simple load generator (stdlib only).

Usage: python scripts/load_test.py --url http://localhost:8000 --rps 20 --duration 120
"""
import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

stats = Counter()
latencies: list[float] = []
lock = threading.Lock()


def one_request(base: str) -> None:
    body = json.dumps({
        "amount": round(random.uniform(1, 5000), 2),
        "currency": "USD",
        "from_account": f"ACC-{random.randint(1000, 9999)}",
        "to_account": f"ACC-{random.randint(1000, 9999)}",
    }).encode()
    req = urllib.request.Request(f"{base}/api/payments", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
            pid = json.loads(r.read())["id"]
        urllib.request.urlopen(f"{base}/api/payments/{pid}", timeout=10).read()
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = "conn_error"
    with lock:
        stats[code] += 1
        latencies.append(time.perf_counter() - start)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--rps", type=int, default=20)
    p.add_argument("--duration", type=int, default=60)
    a = p.parse_args()

    print(f"Sending ~{a.rps} rps to {a.url} for {a.duration}s ... Ctrl+C to stop")
    end = time.time() + a.duration
    try:
        while time.time() < end:
            for _ in range(a.rps):
                threading.Thread(target=one_request, args=(a.url,), daemon=True).start()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    time.sleep(2)
    total = sum(stats.values()) or 1
    lat = sorted(latencies) or [0]
    print("\nResults:", dict(stats))
    print(f"Success rate: {stats[201] / total:.2%}")
    print(f"p50={lat[len(lat)//2]*1000:.0f}ms  p99={lat[int(len(lat)*0.99)-1]*1000:.0f}ms")


if __name__ == "__main__":
    main()
