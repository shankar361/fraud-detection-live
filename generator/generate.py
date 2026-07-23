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
import requests
from dotenv import load_dotenv
load_dotenv()  
from datetime import datetime, timezone

ENGINE_URL= os.getenv("ENGINE_URL", "http://localhost:8000/transactions") 
print(f"Using ENGINE_URL={ENGINE_URL}")
MERCHANT_CATEGORIES = [
    "groceries",
    "electronics",
    "dining",
    "fuel",
    "e-commerce",
    "travel",
    "gift_cards",
    "utilities",
    "streaming",
    "health",
    "fashion",
]
MERCHANTS = {
    "groceries": ["BigBasket", "Local Kirana", "DMart", "Nature's Basket", "Spencer's"],
    "electronics": ["Croma", "Amazon India", "Reliance Digital", "Tata Cliq", "Sony Center"],
    "dining": ["Zomato", "Swiggy", "Local Cafe", "Cafe Coffee Day", "Barbeque Nation"],
    "fuel": ["Indian Oil", "HP Petrol Pump", "Bharat Petroleum"],
    "e-commerce": ["Amazon India", "Flipkart", "Myntra", "Nykaa", "Ajio"],
    "travel": ["MakeMyTrip", "IRCTC", "Ola", "Uber", "Yatra"],
    "gift_cards": ["Amazon Gift Card", "Google Play Recharge", "Flipkart Gift Voucher"],
    "utilities": ["BSES Electricity", "Jio Fiber", "Airtel Payment Bank", "BSNL Internet"],
    "streaming": ["Netflix", "Amazon Prime", "Disney+ Hotstar", "Spotify"],
    "health": ["1mg", "PharmEasy", "Netmeds", "MediBuddy"],
    "fashion": ["Zara", "H&M", "Puma", "Decathlon"],
}

CURRENCY_BY_COUNTRY = {
    "IN": "INR",
    "US": "USD",
    "TH": "THB",
    "AE": "AED",
    "SG": "SGD",
    "GB": "GBP",
    "FR": "EUR",
    "JP": "JPY",
    "AU": "AUD",
}

PAYMENT_METHOD_PREFIXES = ["card_ending_{:04d}", "upi:{user}@okaxis", "wallet_Paytm_{:04d}", "wallet_GooglePay_{:04d}", "wallet_PhonePe_{:04d}"]

CITIES = {
    "Kolkata": (22.5726, 88.3639, "IN"),
    "Mumbai": (19.0760, 72.8777, "IN"),
    "Delhi": (28.7041, 77.1025, "IN"),
    "Bangalore": (12.9716, 77.5946, "IN"),
    "Chennai": (13.0827, 80.2707, "IN"),
    "Bengaluru": (12.9716, 77.5946, "IN"),
    "Hyderabad": (17.3850, 78.4867, "IN"),
    "Pune": (18.5204, 73.8567, "IN"),
    "Bangkok": (13.7563, 100.5018, "TH"),
    "Dubai": (25.2048, 55.2708, "AE"),
    "Singapore": (1.3521, 103.8198, "SG"),
    "London": (51.5074, -0.1278, "GB"),
    "New York": (40.7128, -74.0060, "US"),
    "Paris": (48.8566, 2.3522, "FR"),
    "Tokyo": (35.6762, 139.6503, "JP"),
    "Sydney": (-33.8688, 151.2093, "AU"),
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
        self.backup_device_id = f"device_{uuid.uuid4().hex[:8]}"
        self.payment_methods = [
            PAYMENT_METHOD_PREFIXES[0].format(random.randint(1000, 9999)),
            PAYMENT_METHOD_PREFIXES[1].format(user=self.user_id),
            PAYMENT_METHOD_PREFIXES[2].format(random.randint(1000, 9999)),
        ]

    def normal_transaction(self, device_override: str = None) -> dict:
        category = random.choice(self.preferred_categories)
        merchant = random.choice(MERCHANTS[category])
        lat, lon, country = CITIES[self.home_city]
        lat += random.uniform(-0.01, 0.01)
        lon += random.uniform(-0.01, 0.01)
        amount = round(random.uniform(*self.typical_amount_range), 2)
        device_id = device_override or random.choice([self.device_id, self.backup_device_id])
        payment_method = random.choice(self.payment_methods)
        return self._build(
            category,
            merchant,
            self.home_city,
            lat,
            lon,
            country,
            amount,
            device_id,
            payment_method,
        )

    def anomalous_transaction(self) -> dict:
        """Randomly picks one of several anomaly types."""
        anomaly_type = random.choice([
            "geo_jump",
            "amount_spike",
            "new_payment_method",
            "device_swap",
            "new_category",
        ])

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

        if anomaly_type == "new_payment_method":
            lat, lon, country = CITIES[self.home_city]
            amount = round(random.uniform(*self.typical_amount_range), 2)
            category = random.choice(self.preferred_categories)
            merchant = random.choice(MERCHANTS[category])
            payment_method = f"card_ending_{random.randint(1000, 9999)}"
            return self._build(category, merchant, self.home_city, lat, lon, country, amount, self.device_id, payment_method)

        if anomaly_type == "device_swap":
            category = random.choice(self.preferred_categories)
            merchant = random.choice(MERCHANTS[category])
            lat, lon, country = CITIES[self.home_city]
            amount = round(random.uniform(*self.typical_amount_range), 2)
            return self._build(
                category,
                merchant,
                self.home_city,
                lat,
                lon,
                country,
                amount,
                self.backup_device_id,
            )

        # new_category
        lat, lon, country = CITIES[self.home_city]
        category = random.choice([c for c in MERCHANT_CATEGORIES if c not in self.preferred_categories])
        merchant = random.choice(MERCHANTS[category])
        amount = round(random.uniform(2000, 8000), 2)
        return self._build(category, merchant, self.home_city, lat, lon, country, amount, self.device_id)

    def _build(
        self,
        category,
        merchant,
        city,
        lat,
        lon,
        country,
        amount,
        device_id,
        payment_method: str | None = None,
    ) -> dict:
        currency = CURRENCY_BY_COUNTRY.get(country, "INR")
        payment_method = payment_method or random.choice(self.payment_methods)
        return {
            "transaction_id": f"txn_{uuid.uuid4().hex[:10]}",
            "user_id": self.user_id,
            "amount": amount,
            "currency": currency,
            "merchant": merchant,
            "merchant_category": category,
            "location": {"city": city, "country": country, "lat": lat, "lon": lon},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id,
            "payment_method": payment_method,
        }


RING_DEVICE_IDS = ["device_ring_alpha", "device_ring_beta"]
RING_PARTICIPANT_COUNT = 4  # how many of the synthetic users are "in on" each ring


def send(txn: dict):
    try:
        resp = requests.post(ENGINE_URL, json=txn, timeout=3)
        result = resp.json()
        flag = "FLAGGED" if result.get("is_flagged") else "   ok"
        ring_tag = ""
        if result.get("ring_flag"):
            n = len(result["ring_flag"]["linked_users"])
            ring_tag = f"  [RING: {n} users on {result['ring_flag']['device_id']}]"
        print(f"{flag}  {txn['user_id']:10s} Rs.{txn['amount']:>9.0f}  {txn['location']['city']:10s} "
              f"risk={result.get('risk_score')}  {result.get('reasons')}{ring_tag}")
    except requests.exceptions.RequestException as e:
        print(f"[error] could not reach engine: {e}")


def warm_up_ring(users: list, ring_participant_ids: set):
    """
    Guarantees a ring fires almost immediately instead of leaving it to
    chance. With only a handful of ring participants split across 2
    shared devices and a per-tick probability of routing through one,
    naturally accumulating 3 distinct users on the SAME device can
    realistically take several minutes — too long for a live demo.
    This fires 3 ring participants through the same shared device,
    back to back, right at startup.
    """
    device = RING_DEVICE_IDS[0]
    chosen = [u for u in users if u.user_id in ring_participant_ids][:3]
    print(f"Forcing an early ring on {device} using {[u.user_id for u in chosen]} "
          f"so you see a detection within the first few seconds...\n")
    for u in chosen:
        send(u.normal_transaction(device_override=device))
        time.sleep(1.2)
    print()


def main():
    random.seed()
    users = [SyntheticUser(f"user_{i:03d}") for i in range(15)]

    # Pick a handful of users to be "ring participants" — they occasionally
    # transact from a shared device instead of their own, simulating a
    # mule network / fake-account farm. Everyone else behaves normally.
    ring_participants = random.sample(users, k=RING_PARTICIPANT_COUNT)
    ring_participant_ids = {u.user_id for u in ring_participants}
    print(f"Ring participants (will occasionally share a device): "
          f"{sorted(ring_participant_ids)}\n")

    #warm_up_ring(users, ring_participant_ids)

    print(f"Starting transaction stream for {len(users)} synthetic users. Ctrl+C to stop.\n")

    while True:
        user = random.choice(users)

        if user.user_id in ring_participant_ids and random.random() < 0.35:
            # Route this user's transaction through a shared "ring" device
            # instead of their own — individually this txn looks completely
            # normal, only the graph layer can see it's suspicious.
            shared_device = random.choice(RING_DEVICE_IDS)
            send(user.normal_transaction(device_override=shared_device))
        elif random.random() < 0.12:
            # ~12% chance of a per-transaction anomaly (unrelated to rings)
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