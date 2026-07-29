# routers/cart.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/cart",
    tags=["Cart"]
)

# Helper: Get or create cart for current user
def get_or_create_user_cart(db: Session, user_id: int) -> models.Cart:
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


# Helper: Format cart response with total price calculation
def format_cart_response(cart: models.Cart) -> schemas.CartResponse:
    total_price = sum(item.product.price * item.quantity for item in cart.items if item.product)
    
    # Calculate average rating / count for each product in cart items
    formatted_items = []
    for item in cart.items:
        reviews = item.product.reviews or []
        avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0.0
        
        prod_resp = schemas.ProductResponse.model_validate(item.product)
        prod_resp.average_rating = avg_rating
        prod_resp.review_count = len(reviews)
        
        formatted_items.append({
            "id": item.id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "product": prod_resp
        })

    return schemas.CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=formatted_items,
        total_price=round(total_price, 2)
    )


# 1. Get User Cart
@router.get("/", response_model=schemas.CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cart = get_or_create_user_cart(db, current_user.id)
    return format_cart_response(cart)


# 2. Add Item to Cart
@router.post("/items", response_model=schemas.CartResponse)
def add_to_cart(
    item_data: schemas.CartItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    product = db.query(models.Product).filter(models.Product.id == item_data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = get_or_create_user_cart(db, current_user.id)

    # Check if item already exists in cart
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == item_data.product_id
    ).first()

    if cart_item:
        cart_item.quantity += item_data.quantity
    else:
        cart_item = models.CartItem(
            cart_id=cart.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity
        )
        db.add(cart_item)

    db.commit()
    db.refresh(cart)
    return format_cart_response(cart)


# 3. Update Cart Item Quantity
@router.put("/items/{item_id}", response_model=schemas.CartResponse)
def update_cart_item(
    item_id: int,
    item_data: schemas.CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cart = get_or_create_user_cart(db, current_user.id)
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.cart_id == cart.id
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    if item_data.quantity <= 0:
        db.delete(cart_item)
    else:
        cart_item.quantity = item_data.quantity

    db.commit()
    db.refresh(cart)
    return format_cart_response(cart)


# 4. Delete Item from Cart
@router.delete("/items/{item_id}", response_model=schemas.CartResponse)
def remove_cart_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cart = get_or_create_user_cart(db, current_user.id)
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.cart_id == cart.id
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.delete(cart_item)
    db.commit()
    db.refresh(cart)
    return format_cart_response(cart)


# 5. Clear Entire Cart
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cart = get_or_create_user_cart(db, current_user.id)
    db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).delete()
    db.commit()
    return None