"""
Generates a realistic, continuous stream of fake transactions and POSTs
each one to the fraud engine, simulating live traffic.

Run with:
    python generate.py

Requires the engine to already be running on http://localhost:8000
"""

import os
import random
import time
import uuid
from datetime import datetime, timezone
import requests

ENGINE_URL = os.getenv("ENGINE_URL", "https://fraud-detection-be-ruddy.vercel.app/transactions")

MERCHANT_CATEGORIES = ["groceries", "electronics", "dining", "fuel", "e-commerce", "travel", "gift_cards"]
MERCHANTS = {
    "groceries": ["BigBasket", "Local Kirana", "DMart"],
    "electronics": ["Croma", "Amazon India", "Reliance Digital"],
    "dining": ["Zomato", "Swiggy", "Local Cafe"],
    "fuel": ["Indian Oil", "HP Petrol Pump"],
    "e-commerce": ["Amazon India", "Flipkart", "Myntra"],
    "travel": ["MakeMyTrip", "IRCTC", "Ola"],
    "gift_cards": ["Amazon Gift Card", "Google Play Recharge"],
}

CITIES = {
    "Kolkata": (22.5726, 88.3639, "IN"),
    "Mumbai": (19.0760, 72.8777, "IN"),
    "Delhi": (28.7041, 77.1025, "IN"),
    "Bangalore": (12.9716, 77.5946, "IN"),
    "Bangkok": (13.7563, 100.5018, "TH"),
    "Dubai": (25.2048, 55.2708, "AE"),
}


class SyntheticUser:
    """A fake user with a stable 'normal' behavior profile."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.home_city = random.choice(list(CITIES.keys()))
        self.typical_amount_range = (
            random.uniform(100, 500),
            random.uniform(1000, 4000),
        )
        self.preferred_categories = random.sample(MERCHANT_CATEGORIES, k=3)
        self.device_id = f"device_{uuid.uuid4().hex[:8]}"

    def normal_transaction(self) -> dict:
        category = random.choice(self.preferred_categories)
        merchant = random.choice(MERCHANTS[category])
        lat, lon, country = CITIES[self.home_city]
        lat += random.uniform(-0.01, 0.01)
        lon += random.uniform(-0.01, 0.01)
        amount = round(random.uniform(*self.typical_amount_range), 2)
        return self._build(category, merchant, self.home_city, lat, lon, country, amount, self.device_id)

    def anomalous_transaction(self) -> dict:
        """Randomly picks one of several anomaly types."""
        anomaly_type = random.choice(["geo_jump", "amount_spike", "new_category"])

        if anomaly_type == "geo_jump":
            other_city = random.choice([c for c in CITIES if c != self.home_city])
            lat, lon, country = CITIES[other_city]
            amount = round(random.uniform(*self.typical_amount_range), 2)
            category = random.choice(self.preferred_categories)
            merchant = random.choice(MERCHANTS[category])
            return self._build(category, merchant, other_city, lat, lon, country, amount, self.device_id)

        if anomaly_type == "amount_spike":
            lat, lon, country = CITIES[self.home_city]
            amount = round(self.typical_amount_range[1] * random.uniform(5, 15), 2)
            category = random.choice(self.preferred_categories)
            merchant = random.choice(MERCHANTS[category])
            return self._build(category, merchant, self.home_city, lat, lon, country, amount, self.device_id)

        # new_category
        lat, lon, country = CITIES[self.home_city]
        category = "gift_cards"
        merchant = random.choice(MERCHANTS[category])
        amount = round(random.uniform(2000, 8000), 2)
        return self._build(category, merchant, self.home_city, lat, lon, country, amount, self.device_id)

    def _build(self, category, merchant, city, lat, lon, country, amount, device_id) -> dict:
        return {
            "transaction_id": f"txn_{uuid.uuid4().hex[:10]}",
            "user_id": self.user_id,
            "amount": amount,
            "currency": "INR",
            "merchant": merchant,
            "merchant_category": category,
            "location": {"city": city, "country": country, "lat": lat, "lon": lon},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id,
            "payment_method": "card_ending_" + str(random.randint(1000, 9999)),
        }


def send(txn: dict):
    try:
        resp = requests.post(ENGINE_URL, json=txn, timeout=10)
        if not resp.ok:
            print(f"[error] engine returned HTTP {resp.status_code}: {resp.text[:300]}")
            return
        result = resp.json()
        flag = "FLAGGED" if result.get("is_flagged") else "   ok"
        print(f"{flag}  {txn['user_id']:10s} Rs.{txn['amount']:>9.0f}  {txn['location']['city']:10s} "
              f"risk={result.get('risk_score')}  {result.get('reasons')}")
    except requests.exceptions.ConnectionError:
        print(f"[error] could not reach engine at {ENGINE_URL} — check URL and server status.")
    except requests.exceptions.RequestException as e:
        print(f"[error] request failed: {e}")


def main():
    random.seed()
    users = [SyntheticUser(f"user_{i:03d}") for i in range(15)]

    print(f"Starting transaction stream for {len(users)} synthetic users. Ctrl+C to stop.\n")

    while True:
        user = random.choice(users)

        # ~12% chance of an anomalous transaction
        if random.random() < 0.12:
            if random.random() < 0.3:
                # velocity burst: fire several transactions rapidly for this user
                for _ in range(random.randint(3, 4)):
                    send(user.normal_transaction())
                    time.sleep(random.uniform(1, 3))
            else:
                send(user.anomalous_transaction())
        else:
            send(user.normal_transaction())

        time.sleep(random.uniform(0.8, 2.5))


if __name__ == "__main__":
    main()