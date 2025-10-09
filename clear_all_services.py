#!/usr/bin/env python3
"""Delete all service instances from Redis"""

from redis import Redis

# Connect to Redis
r = Redis(host='redis', port=6379, decode_responses=False)

print("Finding all service instances...")

count = 0
for key in r.scan_iter("*_service_instance"):
    key_str = key.decode('utf-8')
    print(f"Deleting: {key_str}")
    r.delete(key)
    count += 1

print(f"\nDeleted {count} service instances")
