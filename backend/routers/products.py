import json
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
import cloudinary.uploader

import models, schemas
from database import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/products",
    tags=["Products & Reviews"]
)


# Helper: Extract Cloudinary public_id from secure URL to clean up stored images
def extract_cloudinary_public_id(image_url: str) -> Optional[str]:
    if not image_url or "cloudinary.com" not in image_url:
        return None
    match = re.search(r"/(?:v\d+/)?(products/[^/.]+)", image_url)
    if match:
        return match.group(1)
    return None


# Helper: Attach average_rating and review_count to the response
def format_product_response(product: models.Product) -> schemas.ProductResponse:
    reviews = product.reviews or []
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0.0
    
    response = schemas.ProductResponse.model_validate(product)
    response.average_rating = avg_rating
    response.review_count = len(reviews)
    return response


# 1. Fetch All Products (Public)
@router.get("/", response_model=List[schemas.ProductResponse])
def get_products(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return [format_product_response(p) for p in products]


# 2. Fetch Single Product (Public)
@router.get("/{product_id}", response_model=schemas.ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return format_product_response(product)


# 3. Create Product with Cloudinary Image Upload (Protected - JWT required)
@router.post("/", response_model=schemas.ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    title: str = Form(...),
    price: float = Form(...),
    description: Optional[str] = Form(None),
    custom_fields: Optional[str] = Form("[]"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    image_url = None

    if image:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

        try:
            contents = await image.read()
            upload_result = cloudinary.uploader.upload(
                contents,
                folder="products"
            )
            image_url = upload_result.get("secure_url")
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to upload image to Cloudinary: {str(e)}"
            )

    try:
        parsed_custom_fields = json.loads(custom_fields) if custom_fields else []
    except json.JSONDecodeError:
        parsed_custom_fields = []

    new_product = models.Product(
        title=title,
        price=price,
        description=description,
        custom_fields=parsed_custom_fields,
        image_url=image_url,
        user_id=current_user.id
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return format_product_response(new_product)


# 4. Update Product (Protected - Owner only)
@router.put("/{product_id}", response_model=schemas.ProductResponse)
async def update_product(
    product_id: int, 
    title: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    description: Optional[str] = Form(None),
    custom_fields: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to edit this product"
        )
        
    if title is not None:
        product.title = title
    if price is not None:
        product.price = price
    if description is not None:
        product.description = description
    if custom_fields is not None:
        try:
            product.custom_fields = json.loads(custom_fields)
        except json.JSONDecodeError:
            pass

    if image:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

        try:
            old_public_id = extract_cloudinary_public_id(product.image_url)
            if old_public_id:
                cloudinary.uploader.destroy(old_public_id)

            contents = await image.read()
            upload_result = cloudinary.uploader.upload(contents, folder="products")
            product.image_url = upload_result.get("secure_url")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update image on Cloudinary: {str(e)}")

    db.commit()
    db.refresh(product)
    
    return format_product_response(product)


# 5. Delete Product & Associated Cloudinary Image (Protected - Owner only)
@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to delete this product"
        )
        
    if product.image_url:
        public_id = extract_cloudinary_public_id(product.image_url)
        if public_id:
            try:
                cloudinary.uploader.destroy(public_id)
            except Exception:
                pass

    db.delete(product)
    db.commit()
    return None


# 6. Add or Update Review (Protected - JWT required)
@router.post("/{product_id}/reviews", response_model=schemas.ReviewResponse)
def create_or_update_review(
    product_id: int, 
    review: schemas.ReviewCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Verify product exists
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if a review already exists for this user and product
    existing_review = db.query(models.Review).filter(
        models.Review.product_id == product_id,
        models.Review.user_id == current_user.id
    ).first()

    if existing_review:
        # UPDATE existing review
        existing_review.rating = review.rating
        existing_review.comment = review.comment
        db.commit()
        db.refresh(existing_review)
        return existing_review
    else:
        # CREATE new review
        new_review = models.Review(
            rating=review.rating,
            comment=review.comment,
            product_id=product_id,
            user_id=current_user.id
        )
        db.add(new_review)
        db.commit()
        db.refresh(new_review)
        return new_review