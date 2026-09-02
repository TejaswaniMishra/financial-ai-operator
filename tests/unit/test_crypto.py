import pytest
from packages.utils.crypto import hash_password, verify_password
from packages.utils.password_policy import validate_password

def test_hash_password():
    plaintext = "super_secret_password_123"
    hashed = hash_password(plaintext)
    
    assert hashed != plaintext
    assert hashed.startswith("$argon2id$")
    
    # Verify non-determinism (salting works)
    hashed_2 = hash_password(plaintext)
    assert hashed != hashed_2

def test_hash_password_empty_raises():
    with pytest.raises(ValueError, match="Password cannot be empty"):
        hash_password("")
        
def test_verify_password_success():
    plaintext = "correct_horse_battery_staple"
    hashed = hash_password(plaintext)
    assert verify_password(plaintext, hashed) is True

def test_verify_password_failure():
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False

def test_verify_password_empty():
    hashed = hash_password("something")
    assert verify_password("", hashed) is False
    assert verify_password("something", "") is False

def test_validate_password_policy():
    # Valid
    validate_password("123456789012") # 12 chars
    
    # Invalid length
    with pytest.raises(ValueError, match="Password must be at least 12 characters long"):
        validate_password("short")
        
    # Empty
    with pytest.raises(ValueError, match="Password cannot be empty"):
        validate_password("")
        
    # Wrong type
    with pytest.raises(ValueError, match="Password must be a string"):
        validate_password(123456789012)
