import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import cloudinary

# Load environment variables from .env file FIRST
load_dotenv()

import models
from database import engine
from routers import cart, products, auth

# 1. Initialize Cloudinary BEFORE routers run
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

# 2. Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="E-Commerce API")

# 3. Configure CORS
origins = [
    "http://localhost:5173",    # Vite default port
    "http://127.0.0.1:5173",  # Alternative localhost IP
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Mount Modular Routers
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(cart.router, prefix="/api")