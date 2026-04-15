"""
generate_vapid_keys.py — One-time script to generate VAPID keys for Web Push.

Run once:
    pip install pywebpush
    python generate_vapid_keys.py

Copy the output into your .env file.
"""

import base64
from py_vapid import Vapid

vapid = Vapid()
vapid.generate_keys()

# Export private key as base64url-encoded DER
private_key = base64.urlsafe_b64encode(
    vapid.private_key.private_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.DER,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PrivateFormat"]).PrivateFormat.PKCS8,
        encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["NoEncryption"]).NoEncryption(),
    )
).decode("utf-8").rstrip("=")

# Export public key as base64url-encoded uncompressed point
public_key = base64.urlsafe_b64encode(
    vapid.public_key.public_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.X962,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.UncompressedPoint,
    )
).decode("utf-8").rstrip("=")

print("Add these to your .env file:\n")
print(f"VAPID_PRIVATE_KEY={private_key}")
print(f"VAPID_PUBLIC_KEY={public_key}")
print(f"VAPID_EMAIL=mailto:you@example.com")
