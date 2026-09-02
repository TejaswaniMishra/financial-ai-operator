from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database.models.identity import RoleName

class RoleResponse(BaseModel):
    id: str
    name: RoleName
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserRoleResponse(BaseModel):
    id: str
    user_id: str
    role_id: str
    created_at: datetime
    
    role: Optional[RoleResponse] = None

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    roles: List[UserRoleResponse] = []

    class Config:
        from_attributes = True
