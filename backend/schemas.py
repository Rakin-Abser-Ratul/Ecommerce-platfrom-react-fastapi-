from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

# --- USER SCHEMAS ---
class UserMinResponse(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


# --- CUSTOM FIELD SCHEMA ---
class CustomField(BaseModel):
    name: str = Field(..., description="Field label e.g., 'RAM' or 'Color'")
    value: str = Field(..., description="Field value e.g., '16GB' or 'Midnight Slate'")


# --- REVIEW SCHEMAS ---
class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    rating: int
    comment: Optional[str]
    created_at: datetime
    user_id: int
    product_id: int
    user: Optional[UserMinResponse] = None  # Includes minimal user details (id, username)

    model_config = ConfigDict(from_attributes=True)


# --- PRODUCT SCHEMAS ---
class ProductBase(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    custom_fields: List[CustomField] = Field(default_factory=list)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    custom_fields: Optional[List[CustomField]] = None

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    user_id: Optional[int] = None
    
    # Dynamically calculated fields
    average_rating: float = 0.0
    review_count: int = 0
    reviews: List[ReviewResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductResponse  # Reuses your existing ProductResponse

    model_config = ConfigDict(from_attributes=True)

class CartResponse(BaseModel):
    id: int
    user_id: int
    items: List[CartItemResponse] = []
    total_price: float = 0.0

    model_config = ConfigDict(from_attributes=True)