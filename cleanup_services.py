#!/usr/bin/env python3
"""Clean up corrupt service instances from Redis"""

import json
from redis import Redis

# Connect to Redis
r = Redis(host='redis', port=6379, decode_responses=False)

print("Scanning for service instances...")

corrupt_count = 0
valid_count = 0

for key in r.scan_iter("*_service_instance"):
    key_str = key.decode('utf-8')
    data = r.get(key)

    if not data:
        print(f"Empty data for key: {key_str}")
        print(f"  Deleting...")
        r.delete(key)
        corrupt_count += 1
        continue

    try:
        # Try to parse as JSON
        parsed = json.loads(data)
        print(f"Valid: {key_str}")
        valid_count += 1
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Corrupt data for key: {key_str}")
        print(f"  Data type: {type(data)}")
        print(f"  Error: {e}")
        print(f"  Deleting...")
        r.delete(key)
        corrupt_count += 1

print(f"\nSummary:")
print(f"  Valid instances: {valid_count}")
print(f"  Corrupt instances deleted: {corrupt_count}")
