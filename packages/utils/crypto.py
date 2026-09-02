from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Using default argon2id parameters recommended by current RFCs
_ph = PasswordHasher()

def hash_password(plaintext: str) -> str:
    """
    Securely hashes a plaintext password using Argon2id.
    Never logs or exposes the plaintext inside the hashing function.
    """
    if not plaintext:
        raise ValueError("Password cannot be empty")
    return _ph.hash(plaintext)

def verify_password(plaintext: str, hashed: str) -> bool:
    """
    Verifies a plaintext password against a stored Argon2id hash.
    Returns True if valid, False otherwise.
    """
    if not plaintext or not hashed:
        return False
        
    try:
        return _ph.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False
