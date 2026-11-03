from __future__ import annotations

import csv
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics import ANOMALY_THRESHOLD, WEIGHT_PROFILES, enrich_products, rank_products
from database import Base, SessionLocal, engine, get_db
from models import Product
from schemas import ProductCreate, ProductOut, ProductUpdate


BASE_DIR = Path(__file__).resolve().parent

SAMPLE_PRODUCTS = [
    {"category": "Laptop", "title": "Laptop A", "price": 22000, "age": 2, "condition": "Good", "original_price": 45000},
    {"category": "Laptop", "title": "Laptop B", "price": 18000, "age": 3, "condition": "Average", "original_price": 42000},
    {"category": "Laptop", "title": "Laptop C", "price": 25000, "age": 1, "condition": "Excellent", "original_price": 48000},
    {"category": "Laptop", "title": "Laptop D", "price": 20000, "age": 2, "condition": "Good", "original_price": 40000},
    {"category": "Laptop", "title": "Laptop E", "price": 15000, "age": 4, "condition": "Average", "original_price": 38000},
    {"category": "Bicycle", "title": "Riverside City Bike", "price": 6800, "age": 2, "condition": "Good", "original_price": 14500},
    {"category": "Bicycle", "title": "Rockrider MTB", "price": 9700, "age": 1, "condition": "Excellent", "original_price": 21000},
    {"category": "Bicycle", "title": "Hero Sprint", "price": 5200, "age": 3, "condition": "Average", "original_price": 11000},
    {"category": "Bicycle", "title": "Premium Carbon Cycle", "price": 26500, "age": 2, "condition": "Good", "original_price": 39000},
    {"category": "Book", "title": "Data Structures in Python", "price": 620, "age": 1, "condition": "Excellent", "original_price": 1200},
    {"category": "Book", "title": "Engineering Mathematics III", "price": 350, "age": 2, "condition": "Good", "original_price": 780},
    {"category": "Book", "title": "Operating System Concepts", "price": 480, "age": 3, "condition": "Average", "original_price": 1100},
    {"category": "Book", "title": "Computer Networks Handbook", "price": 900, "age": None, "condition": "Good", "original_price": 1500},
    {"category": "Gadget", "title": "Casio Scientific Calculator", "price": 720, "age": 2, "condition": "Good", "original_price": 1350},
    {"category": "Gadget", "title": "Wireless Keyboard", "price": 1100, "age": 1, "condition": "Excellent", "original_price": 2200},
    {"category": "Gadget", "title": "USB-C Hub 7-in-1", "price": 1250, "age": 1, "condition": "Good", "original_price": 2800},
    {"category": "Gadget", "title": "Noise-Cancelling Headphones", "price": 3200, "age": 2, "condition": None, "original_price": 6500},
    {"category": "Furniture", "title": "Study Table", "price": 2400, "age": 3, "condition": "Good", "original_price": 5200},
    {"category": "Furniture", "title": "Ergonomic Chair", "price": 3500, "age": 2, "condition": "Excellent", "original_price": 7000},
    {"category": "Furniture", "title": "Bookshelf", "price": 1800, "age": 4, "condition": "Average", "original_price": None},
]


def seed_database() -> None:
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Product))
        if count == 0:
            db.add_all([Product(**item) for item in SAMPLE_PRODUCTS])
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield


app = FastAPI(
    title="CampusLoop Smart Marketplace",
    description="Explainable, budget-aware recommendations for student resale listings.",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/products")
def list_products(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    category: str | None = None,
    max_budget: Annotated[float | None, Query(gt=0)] = None,
):
    statement = select(Product)
    if search and search.strip():
        statement = statement.where(Product.title.ilike(f"%{search.strip()}%"))
    if category and category.strip():
        statement = statement.where(func.lower(Product.category) == category.strip().lower())
    if max_budget is not None:
        statement = statement.where(Product.price <= max_budget)
    products = db.scalars(statement.order_by(Product.category, Product.price)).all()
    return enrich_products(products)


@app.get("/api/categories")
def list_categories(db: Annotated[Session, Depends(get_db)]):
    categories = db.scalars(select(Product.category).distinct().order_by(Product.category)).all()
    return {"categories": categories}


@app.post("/api/products", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.put("/api/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    db.delete(product)
    db.commit()


@app.get("/api/recommendations")
def recommendations(
    db: Annotated[Session, Depends(get_db)],
    budget: Annotated[float, Query(gt=0)] = 23000,
    priority: Annotated[str, Query(pattern="^(balanced|affordability|condition)$")] = "balanced",
    category: Annotated[str, Query(min_length=1)] = "Laptop",
):
    products = db.scalars(select(Product).order_by(Product.id)).all()
    return rank_products(products, budget=budget, priority=priority, category=category)


@app.get("/api/formula")
def formula_details():
    return {
        "profiles": {
            name: {factor: round(weight * 100) for factor, weight in weights.items()}
            for name, weights in WEIGHT_PROFILES.items()
        },
        "price_component": "100 × (1 - selling price / buyer budget), clamped to 0–100",
        "age_component": "100 × (1 - age / 10 years), clamped to 0–100",
        "condition_component": "Excellent 100, Good 80, Average 60, Fair 35, Poor 15",
        "missing_values": "Missing age or condition receives a neutral score of 50. Missing original price omits only the price/original indicator.",
        "ties": "Higher condition score, then lower price, younger age, and finally listing ID.",
        "anomaly_rule": f"Flag when price differs by more than {ANOMALY_THRESHOLD:.0%} from the category median and at least 3 comparable listings exist.",
    }


def _optional_float(value, field_name: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def _normalize_row(row: dict) -> dict:
    def normalize_key(key) -> str:
        return (
            str(key)
            .strip()
            .lower()
            .replace("₹", "")
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "_")
            .replace("-", "_")
            .strip("_")
        )

    def first_value(*keys):
        for key in keys:
            value = normalized.get(key)
            if value is not None and str(value).strip() != "":
                return value
        return None

    normalized = {normalize_key(key): value for key, value in row.items()}
    return {
        "category": normalized.get("category"),
        "title": first_value("title", "item", "name"),
        "price": _optional_float(normalized.get("price"), "price"),
        "age": _optional_float(first_value("age", "age_years"), "age"),
        "condition": normalized.get("condition") or None,
        "original_price": _optional_float(
            first_value("original_price", "original"),
            "original_price",
        ),
    }


@app.post("/api/import", status_code=201)
async def import_listings(
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Upload a .csv or .json file")
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="File must be smaller than 2 MB")

    try:
        text = raw.decode("utf-8-sig")
        if filename.endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(text)))
        else:
            parsed = json.loads(text)
            rows = parsed.get("listings", []) if isinstance(parsed, dict) else parsed
        if not isinstance(rows, list):
            raise ValueError("The file must contain a list of product objects")
        if len(rows) > 500:
            raise ValueError("A maximum of 500 listings can be imported at once")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    valid_products = []
    errors = []
    duplicate_count = 0
    existing_signatures = {
        (
            product.category.casefold(),
            product.title.casefold(),
            round(float(product.price), 2),
            product.age,
            product.condition,
            product.original_price,
        )
        for product in db.scalars(select(Product)).all()
    }
    for index, row in enumerate(rows, start=2 if filename.endswith(".csv") else 1):
        try:
            if not isinstance(row, dict):
                raise ValueError("Each listing must be an object")
            payload = ProductCreate.model_validate(_normalize_row(row))
            signature = (
                payload.category.casefold(),
                payload.title.casefold(),
                round(float(payload.price), 2),
                payload.age,
                payload.condition,
                payload.original_price,
            )
            if signature in existing_signatures:
                duplicate_count += 1
                continue
            existing_signatures.add(signature)
            valid_products.append(Product(**payload.model_dump()))
        except (ValidationError, ValueError, TypeError) as exc:
            errors.append({"row": index, "message": str(exc)})

    if not rows:
        raise HTTPException(status_code=422, detail="The file does not contain any listings")
    if not valid_products and duplicate_count == 0:
        raise HTTPException(
            status_code=422,
            detail={"message": "No valid listings found", "errors": errors[:10]},
        )
    if valid_products:
        db.add_all(valid_products)
        db.commit()

    imported_count = len(valid_products)
    invalid_count = len(errors)
    if imported_count:
        message = f"{imported_count} new listing(s) imported successfully."
    else:
        message = "No new listings were added because every valid row already exists."
    return {
        "imported": imported_count,
        "skipped": duplicate_count + invalid_count,
        "duplicates": duplicate_count,
        "invalid": invalid_count,
        "message": message,
        "errors": errors[:10],
    }


@app.get("/sample.csv", include_in_schema=False)
def download_sample_csv():
    return FileResponse(
        BASE_DIR / "data" / "sample_products.csv",
        media_type="text/csv",
        filename="campusloop_sample_products.csv",
    )
