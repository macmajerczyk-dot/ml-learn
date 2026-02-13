"""Simple load test script to send concurrent prediction requests to the gateway.

Usage:
    python scripts/load_test.py --url http://localhost:8000 --requests 100 --concurrency 10
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time

import httpx

SAMPLE_TEXTS = [
    "This product is absolutely amazing! Best purchase I've ever made.",
    "Terrible experience. The item broke after one day of use.",
    "It's okay, nothing special but does the job.",
    "I love this so much, highly recommend to everyone!",
    "Worst customer service I've ever dealt with. Never again.",
    "Pretty good value for the price. Satisfied with my purchase.",
    "The quality is outstanding. Exceeded all my expectations.",
    "Complete waste of money. Do not buy this product.",
    "Decent product with some minor flaws. Would consider buying again.",
    "Absolutely horrible. Arrived damaged and smelled terrible.",
]


async def send_request(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> dict:
    text = random.choice(SAMPLE_TEXTS)
    async with semaphore:
        start = time.perf_counter()
        try:
            resp = await client.post(
                f"{url}/predict",
                json={"text": text},
                timeout=10.0,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "status_code": resp.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
                "request_id": resp.json().get("request_id", ""),
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "status_code": 0,
                "elapsed_ms": round(elapsed_ms, 2),
                "error": str(exc),
            }


async def run_load_test(url: str, num_requests: int, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    print(f"Sending {num_requests} requests to {url} (concurrency={concurrency})")
    print("-" * 60)

    async with httpx.AsyncClient() as client:
        start = time.perf_counter()
        tasks = [send_request(client, url, semaphore) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start

    # Analyze results
    successes = [r for r in results if r["status_code"] == 202]
    failures = [r for r in results if r["status_code"] != 202]
    latencies = [r["elapsed_ms"] for r in successes]

    print(f"\nResults ({total_time:.2f}s total):")
    print(f"  Successful: {len(successes)}/{num_requests}")
    print(f"  Failed:     {len(failures)}/{num_requests}")
    if latencies:
        latencies.sort()
        print(f"  Throughput:  {len(successes) / total_time:.1f} req/s")
        print(f"  Latency p50: {latencies[len(latencies) // 2]:.1f} ms")
        print(f"  Latency p95: {latencies[int(len(latencies) * 0.95)]:.1f} ms")
        print(f"  Latency p99: {latencies[int(len(latencies) * 0.99)]:.1f} ms")
        print(f"  Latency max: {max(latencies):.1f} ms")

    if failures:
        print("\nSample failures:")
        for f in failures[:5]:
            print(f"  {f}")

    # Poll for results
    print("\nPolling for inference results (waiting 15s)...")
    await asyncio.sleep(15)
    completed = 0
    async with httpx.AsyncClient() as client:
        for r in successes[:20]:  # Check first 20
            resp = await client.get(f"{url}/predict/{r['request_id']}")
            data = resp.json()
            if data.get("status") == "completed":
                completed += 1
                print(f"  {r['request_id'][:8]}... → {data['label']} ({data['score']:.4f})")
    print(f"\n  Completed: {completed}/20 sampled")


def main():
    parser = argparse.ArgumentParser(description="Load test the ML pipeline gateway")
    parser.add_argument("--url", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--requests", type=int, default=50, help="Number of requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent requests")
    args = parser.parse_args()

    asyncio.run(run_load_test(args.url, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
