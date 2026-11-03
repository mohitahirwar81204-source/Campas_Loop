from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable


CONDITION_SCORES = {
    "Excellent": 1.0,
    "Good": 0.8,
    "Average": 0.6,
    "Fair": 0.35,
    "Poor": 0.15,
}

WEIGHT_PROFILES = {
    "balanced": {"price": 0.45, "age": 0.20, "condition": 0.35},
    "affordability": {"price": 0.65, "age": 0.15, "condition": 0.20},
    "condition": {"price": 0.20, "age": 0.20, "condition": 0.60},
}

ANOMALY_THRESHOLD = 0.35
MIN_COMPARABLE_ITEMS = 3
MAX_AGE_YEARS = 10.0


def _as_dict(product: Any) -> dict[str, Any]:
    if isinstance(product, dict):
        return dict(product)
    return {
        "id": product.id,
        "category": product.category,
        "title": product.title,
        "price": product.price,
        "age": product.age,
        "condition": product.condition,
        "original_price": product.original_price,
    }


def _round_or_none(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def enrich_products(products: Iterable[Any]) -> list[dict[str, Any]]:
    """Add price indicators and a transparent within-category anomaly flag."""
    items = [_as_dict(product) for product in products]
    grouped_prices: dict[str, list[float]] = defaultdict(list)
    for item in items:
        grouped_prices[item["category"].casefold()].append(float(item["price"]))

    category_stats: dict[str, tuple[float, int]] = {
        category: (float(median(prices)), len(prices))
        for category, prices in grouped_prices.items()
    }

    enriched = []
    for item in items:
        category_median, comparable_count = category_stats[item["category"].casefold()]
        deviation = (
            abs(float(item["price"]) - category_median) / category_median
            if category_median
            else 0.0
        )
        can_compare = comparable_count >= MIN_COMPARABLE_ITEMS
        is_unusual = can_compare and deviation > ANOMALY_THRESHOLD

        original = item.get("original_price")
        price_ratio = float(item["price"]) / float(original) if original else None
        anomaly_reason = None
        if not can_compare:
            anomaly_reason = (
                f"Only {comparable_count} comparable item(s); at least "
                f"{MIN_COMPARABLE_ITEMS} are required to flag unusual prices."
            )
        elif is_unusual:
            direction = "above" if item["price"] > category_median else "below"
            anomaly_reason = (
                f"Price is {deviation:.0%} {direction} the {item['category']} "
                f"median of ₹{category_median:,.0f}. This is a review signal, "
                "not proof of fraud; specifications and seller circumstances may differ."
            )

        enriched.append(
            {
                **item,
                "price_ratio": _round_or_none(price_ratio, 3),
                "category_median": round(category_median, 2),
                "median_deviation": round(deviation, 3),
                "comparable_count": comparable_count,
                "is_unusual": is_unusual,
                "anomaly_reason": anomaly_reason,
            }
        )
    return enriched


def rank_products(
    products: Iterable[Any],
    budget: float,
    priority: str = "balanced",
    category: str | None = None,
) -> dict[str, Any]:
    """Rank eligible products with documented, deterministic scoring and tie rules."""
    if budget <= 0:
        raise ValueError("Budget must be greater than zero")
    if priority not in WEIGHT_PROFILES:
        raise ValueError(f"Unknown priority: {priority}")

    enriched = enrich_products(products)
    selected_category = category.casefold() if category else None
    eligible = [
        item
        for item in enriched
        if float(item["price"]) <= budget
        and (
            selected_category is None
            or item["category"].casefold() == selected_category
        )
    ]

    # Imported files can contain an exact copy of an existing listing. Keep the
    # earliest record for ranking so the top three never repeats one product.
    unique_eligible = []
    seen_listings = set()
    for item in eligible:
        signature = (
            item["category"].casefold(),
            item["title"].casefold(),
            round(float(item["price"]), 2),
            item.get("age"),
            item.get("condition"),
            item.get("original_price"),
        )
        if signature in seen_listings:
            continue
        seen_listings.add(signature)
        unique_eligible.append(item)
    eligible = unique_eligible

    weights = WEIGHT_PROFILES[priority]
    ranked = []
    for item in eligible:
        price_score = max(0.0, min(1.0, 1.0 - float(item["price"]) / budget))
        age_missing = item.get("age") is None
        age_score = (
            0.5
            if age_missing
            else max(0.0, min(1.0, 1.0 - float(item["age"]) / MAX_AGE_YEARS))
        )
        condition_missing = not item.get("condition")
        condition_score = (
            0.5
            if condition_missing
            else CONDITION_SCORES.get(item["condition"], 0.5)
        )
        total = 100 * (
            weights["price"] * price_score
            + weights["age"] * age_score
            + weights["condition"] * condition_score
        )

        savings = budget - float(item["price"])
        reasons = [f"₹{savings:,.0f} under your ₹{budget:,.0f} budget"]
        if item.get("price_ratio") is not None:
            reasons.append(
                f"priced at {item['price_ratio']:.0%} of its original price"
            )
        if age_missing:
            reasons.append("age is missing, so a neutral age score was used")
        else:
            reasons.append(f"{float(item['age']):g} year(s) old")
        if condition_missing:
            reasons.append("condition is missing, so a neutral condition score was used")
        else:
            reasons.append(f"listed in {item['condition'].lower()} condition")

        ranked.append(
            {
                **item,
                "score": round(total, 2),
                "component_scores": {
                    "price": round(price_score * 100, 1),
                    "age": round(age_score * 100, 1),
                    "condition": round(condition_score * 100, 1),
                },
                "explanation": "; ".join(reasons) + ".",
                "missing_fields": [
                    field
                    for field, missing in (
                        ("age", age_missing),
                        ("condition", condition_missing),
                        ("original_price", item.get("original_price") is None),
                    )
                    if missing
                ],
            }
        )

    # Explicit tie-breaks: condition, then lower price, younger age, then ID.
    ranked.sort(
        key=lambda item: (
            -item["score"],
            -item["component_scores"]["condition"],
            float(item["price"]),
            float(item["age"]) if item.get("age") is not None else float("inf"),
            item.get("id", 0),
        )
    )

    return {
        "priority": priority,
        "budget": budget,
        "category": category,
        "weights": {key: round(value * 100) for key, value in weights.items()},
        "formula": (
            "Score = price weight × budget affordability + age weight × age "
            "score + condition weight × condition score. Each component is "
            "normalized to 0–100."
        ),
        "eligible_count": len(ranked),
        "recommendations": ranked[:3],
    }
