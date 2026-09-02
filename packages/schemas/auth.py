from pydantic import BaseModel, Field

class SignupRequest(BaseModel):
    email: str = Field(
        ..., 
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="Must be a valid email structure"
    )
    password: str = Field(
        ..., 
        min_length=12, 
        description="Must be at least 12 characters"
    )
    display_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255
    )

    def normalize_email(self) -> str:
        """Deterministically normalize the email address."""
        return self.email.lower().strip()
