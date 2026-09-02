def validate_password(password: str) -> None:
    """
    Enforces the application's strict password policy.
    Raises ValueError if policy requirements are not met.
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string")
        
    if not password:
        raise ValueError("Password cannot be empty")
        
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
