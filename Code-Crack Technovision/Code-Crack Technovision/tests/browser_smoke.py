"""Optional end-to-end browser verification for a locally running CampusLoop app."""

from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8000"
SCREENSHOT_DIR = Path.home() / "AppData" / "Local" / "Temp"
TEST_TITLE = "Browser QA Calculator"


def clean_test_listings() -> None:
    response = httpx.get(
        f"{BASE_URL}/api/products",
        params={"search": "Browser QA"},
        timeout=10,
    )
    response.raise_for_status()
    for product in response.json():
        httpx.delete(f"{BASE_URL}/api/products/{product['id']}", timeout=10).raise_for_status()


def run() -> None:
    clean_test_listings()
    initial_products = httpx.get(f"{BASE_URL}/api/products", timeout=10).json()
    expected_count = len(initial_products)
    expected_laptops = sum(item["category"] == "Laptop" for item in initial_products)
    expected_books = sum(item["category"] == "Book" for item in initial_products)
    expected_bicycles = sum(item["category"] == "Bicycle" for item in initial_products)
    expected_excellent_laptops = sum(
        item["category"] == "Laptop" and item["condition"] == "Excellent"
        for item in initial_products
    )
    expected_laptop_d = sum(item["title"].lower() == "laptop d" for item in initial_products)
    expected_under_7000 = sum(item["price"] <= 7000 for item in initial_products)
    console_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.goto(BASE_URL, wait_until="networkidle")

            assert page.locator("#recommendationCategory").input_value() == "Laptop"
            assert page.locator(".recommendation-card").count() == 3
            recommendation_titles = page.locator(".recommendation-card h3").all_inner_texts()
            assert len(recommendation_titles) == len(set(recommendation_titles))
            assert page.locator(".lab-card").count() == 2
            assert "Laptop listings only" in page.locator("#comparisonScope").inner_text()
            if page.locator(".product-card").count() != expected_count:
                raise AssertionError(
                    f"Expected {expected_count} product cards, found {page.locator('.product-card').count()}; "
                    f"console errors: {console_errors}"
                )
            assert page.locator(".product-card").count() == expected_count

            page.locator("#importInput").set_input_files("data/sample_products.csv")
            page.locator("#toastMessage").filter(has_text="already exist").wait_for()
            assert page.locator(".product-card").count() == expected_count

            for query, expected in (
                ("books", expected_books),
                ("cycles", expected_bicycles),
                ("excellent laptop", expected_excellent_laptops),
                ("laptop d", expected_laptop_d),
            ):
                page.locator("#headerSearch").fill(query)
                assert page.locator(".product-card").count() == expected
            page.locator("#headerSearch").press("Enter")
            page.wait_for_timeout(700)
            marketplace_top = page.locator("#marketplace").bounding_box()["y"]
            header_height = page.locator(".commerce-header").bounding_box()["height"]
            assert marketplace_top >= header_height
            page.locator("#headerSearch").fill("")

            page.locator("#marketBudgetInput").fill("7000")
            assert page.locator("#budgetOnly").is_checked()
            assert page.locator("#budgetInput").input_value() == "7000"
            assert "7,000" in page.locator("#budgetLabel").inner_text()
            assert page.locator(".product-card").count() == expected_under_7000
            page.locator("#clearFilters").click()
            assert page.locator("#marketBudgetInput").input_value() == "23000"
            assert page.locator(".product-card").count() == expected_count

            affordability_pick = page.locator(".lab-card.affordability strong").inner_text()
            condition_pick = page.locator(".lab-card.condition strong").inner_text()
            assert affordability_pick != condition_pick

            page.locator("#headerSearch").fill("Laptop")
            assert page.locator(".product-card").count() == expected_laptops
            page.locator("#headerSearch").fill("")
            page.locator("#categoryFilter").select_option("Book")
            assert page.locator(".product-card").count() == expected_books
            page.locator("#categoryFilter").select_option("")
            page.locator("#sortFilter").select_option("price-low")
            prices = page.locator(".product-card").evaluate_all(
                "cards => cards.map(card => Number(card.dataset.price))"
            )
            assert prices == sorted(prices)
            page.locator("#sortFilter").select_option("default")

            page.locator("#formulaButton").click()
            assert page.locator("#formulaDialog").evaluate("element => element.open")
            page.locator('[data-close="formulaDialog"]').last.click()

            page.locator("#heroAddButton").click()
            page.locator("#titleField").fill(TEST_TITLE)
            page.locator("#categoryField").fill("Gadget")
            page.locator("#conditionField").select_option("Good")
            page.locator("#priceField").fill("800")
            page.locator("#originalPriceField").fill("1600")
            page.locator("#ageField").fill("1")
            page.locator("#saveListingButton").click()
            page.locator("#listingDialog").wait_for(state="hidden")

            page.locator("#searchInput").fill(TEST_TITLE)
            assert page.locator(".product-card").count() == 1
            page.locator("#productGrid [data-edit-id]").click()
            page.locator("#titleField").fill(f"{TEST_TITLE} Updated")
            page.locator("#saveListingButton").click()
            page.locator("#listingDialog").wait_for(state="hidden")

            clean_test_listings()
            page.reload(wait_until="networkidle")
            assert page.locator(".product-card").count() == expected_count
            page.locator(".product-card [data-shortlist-id]").first.click()
            assert page.locator(".product-card .heart-button.active").count() == 1
            page.screenshot(path=SCREENSHOT_DIR / "campusloop-desktop.png", full_page=True)

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.goto(BASE_URL, wait_until="networkidle")
            dimensions = mobile.evaluate(
                "({client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
            )
            mobile.screenshot(path=SCREENSHOT_DIR / "campusloop-mobile.png", full_page=True)
            if dimensions["scroll"] > dimensions["client"]:
                overflow = mobile.evaluate(
                    "[...document.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).slice(0, 10).map(e => ({tag:e.tagName, cls:e.className, right:Math.round(e.getBoundingClientRect().right), width:Math.round(e.getBoundingClientRect().width)}))"
                )
                raise AssertionError(f"Mobile overflow {dimensions}; elements: {overflow}")
            assert mobile.locator(".recommendation-card").count() == 3
            assert mobile.locator(".product-card").count() == expected_count

            mobile.close()
            browser.close()

        assert not console_errors, f"Browser console errors: {console_errors}"
        print("Browser QA: PASS")
        print(f"Priority shift: {affordability_pick} -> {condition_pick}")
        print("Desktop search/budget/import/listing/filter/dialog/add/edit checks: PASS")
        print("Mobile overflow and responsive recommendation checks: PASS")
        print(f"Screenshots: {SCREENSHOT_DIR / 'campusloop-desktop.png'}")
        print(f"Screenshots: {SCREENSHOT_DIR / 'campusloop-mobile.png'}")
    finally:
        clean_test_listings()


if __name__ == "__main__":
    run()
