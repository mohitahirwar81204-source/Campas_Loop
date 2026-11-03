# CampusLoop — Smart Student Marketplace

CampusLoop is a FastAPI marketplace prototype for the CODE CRACK 3.0 third-year problem statement. It lets students manage second-hand listings, compare prices within sensible categories, and receive transparent top-three recommendations based on their budget and priorities.

The interface uses an original large-marketplace design with global search, category navigation, responsive product cards, discount indicators, sorting, shortlisting, seller forms, and an explainable recommendation lab. It is inspired by modern commerce patterns without copying another platform's branding.

## Technology

- HTML5, responsive CSS, and vanilla JavaScript
- Python 3.10+ with FastAPI and Uvicorn
- Jinja2 templates
- SQLAlchemy with a local SQLite database
- CSV and JSON import

No payment service, seller authentication, machine-learning model, or external API is used.

## Run the application

From PowerShell in this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>.

If the Anaconda Python installation is being used directly:

```powershell
& 'C:\Users\Admin\anaconda3\python.exe' -m uvicorn main:app --reload
```

The SQLite database and 20 demonstration listings are created automatically on first launch. Existing local data is preserved on subsequent launches.

## Requirement coverage

| Requirement | Implementation |
|---|---|
| Load and display listings | SQLite-backed responsive marketplace product grid |
| Add and edit locally | Modal form and FastAPI CRUD endpoints |
| Search and filtering | Category-aware token search, category selector, synchronized maximum-budget input, and budget toggle |
| CSV/JSON input | File importer with validation and partial-error reporting |
| Price indicator | Selling price divided by original price |
| Documented ranking | Price, age, and condition components with visible weights |
| Top three with reasons | Recommendation cards show rank, components, and plain-language reason |
| Unusual price rule | More than 35% from within-category median, requiring 3+ items |
| Priority demonstration | Balanced, affordability-first, and condition-first modes |
| Missing values | Neutral score of 50 for missing age/condition; unavailable ratio for missing original price |
| Identical scores | Condition, lower price, younger age, then listing ID |
| Duplicate imports | Exact duplicates are skipped; ranking never repeats an identical listing |
| Small categories | No anomaly flag with fewer than 3 comparable listings |

## Ranking formula

Only listings at or below the buyer's budget and in one selected, comparable category are eligible. The interface intentionally prevents cross-category recommendations, so a low-priced book is never ranked against a laptop or bicycle.

```text
final score =
  price weight × affordability score
  + age weight × age score
  + condition weight × condition score
```

Each component is normalized to 0–100:

- `affordability = 100 × (1 - selling price / budget)`, clamped to 0–100
- `age = 100 × (1 - age / 10)`, clamped to 0–100
- condition: Excellent 100, Good 80, Average 60, Fair 35, Poor 15

Weight profiles:

| Profile | Price | Age | Condition |
|---|---:|---:|---:|
| Balanced | 45% | 20% | 35% |
| Affordability | 65% | 15% | 20% |
| Condition | 20% | 20% | 60% |

This is a deterministic recommendation aid, not a statement that one product is objectively best. Product specifications are intentionally not invented when absent from the dataset.

## Import format

CSV headers may use `category`, `title` (also `item` or `name`), `price`, `age`, `condition`, and `original_price`. The PDF-style headers `Price ₹`, `Age (years)`, and `Original ₹` are also accepted. JSON may be an array of listing objects or an object containing a `listings` array.

Required values are category, title, and a positive selling price. Age, condition, and original price may be empty. A sample is available in [`data/sample_products.csv`](data/sample_products.csv).

Exact duplicate rows are skipped safely. If an uploaded file contains only listings that already exist, the upload succeeds with an informative “no new listings” message instead of being reported as an invalid file.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests cover within-category anomaly detection, too-small categories, priority changes, missing values, budget/category eligibility, and deterministic tie handling.

With Playwright installed and the development server running, the optional end-to-end check exercises the actual interface, add/edit workflow, filters, dialogs, priority comparison, and mobile layout:

```powershell
pip install -r requirements-dev.txt
playwright install chromium
python tests/browser_smoke.py
```

The full requirement-by-requirement result is recorded in [`VERIFICATION.md`](VERIFICATION.md).
