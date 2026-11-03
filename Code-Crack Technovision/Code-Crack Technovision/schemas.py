from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_CONDITIONS = {"Excellent", "Good", "Average", "Fair", "Poor"}


class ProductBase(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    price: float = Field(gt=0)
    age: float | None = Field(default=None, ge=0, le=100)
    condition: str | None = None
    original_price: float | None = Field(default=None, gt=0)

    @field_validator("category", "title")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("condition")
    @classmethod
    def normalize_condition(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().title()
        if normalized not in ALLOWED_CONDITIONS:
            allowed = ", ".join(sorted(ALLOWED_CONDITIONS))
            raise ValueError(f"Condition must be one of: {allowed}")
        return normalized


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
