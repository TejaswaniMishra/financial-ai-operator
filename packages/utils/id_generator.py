import secrets
import time
import uuid


def generate_id(prefix: str = "id") -> str:
    """
    Generate a time-ordered, collision-resistant prefixed identifier.
    Format: <prefix>_<timestamp_hex><random_hex>
    Examples:
      - tx_18d9f482a91a4f0b
      - rec_18d9f482a91a4f0b
      - aud_18d9f482a91a4f0b
    """
    timestamp = int(time.time() * 1000)
    time_hex = hex(timestamp)[2:]
    rand_hex = secrets.token_hex(6)
    return f"{prefix}_{time_hex}{rand_hex}"


def generate_uuid() -> str:
    """Generate a standard RFC 4122 UUID4 string."""
    return str(uuid.uuid4())
