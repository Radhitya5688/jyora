# Jyora

Jyora is an independent Django food-ordering and restaurant-intelligence demo. It uses server-rendered templates, SQLite by default, and no JavaScript build system. This implementation is a functional student project baseline with database-backed discovery, menu browsing, session cart, server-calculated checkout, persisted orders, owner prep controls, demo rider dispatch, FoodWise comparisons and provisional ETA Trust ranges.

## Windows PowerShell setup

```powershell
cd "C:\Users\radhi\OneDrive\Documents\ChatGPT\JYORA Resturants\jyora"
py -3.13 -m venv --without-pip .venv
.\.venv\Scripts\Activate.ps1
py -3.13 -m pip --python .venv install -r requirements.txt
Copy-Item .env.example .env
python manage.py makemigrations core
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```

Open http://127.0.0.1:8000. Django admin is at `/admin/`. Demo data seeds 10 restaurants, 8 dishes per kitchen, four simulated riders and two sample orders. Local demo accounts are `demo_owner` / `JyoraDemo2026!` and `demo_customer` / `JyoraDemo2026!`; the owner controls Udupi House. Change these passwords before sharing a demo. Customers can also register. Demo passwords are only set when each account is created.

## Architecture

- `config/`: project settings and URL routing.
- `core/models.py`: restaurant, menu, order, history event, rider and favorite records.
- `core/views.py`: server-rendered customer and owner workflows with authentication and ownership checks.
- `core/services.py`: transparent checkout, ETA and demo dispatch logic.
- `core/management/commands/seed_demo_data.py`: repeatable local catalog seed.
- `templates/` and `static/`: responsive Bootstrap-based interface and Jyora visual styles.

## Signature features

**FoodWise** ranks database-backed exact-name dish matches with an editable weight map in `core/services.py`: affordability 35%, restaurant rating 25%, portion 20%, delivery cost 10%, speed 10%. Scores normalize across comparison results and weights are renormalized if portions are unavailable; missing portion data is never fabricated. Comparisons show demo taxes/fees and estimated final cost. Name matching is approximate and does not establish nutritional equivalence.

**KitchenSync** provides a restaurant-owner queue, permitted status steps, readiness timestamps and a simulated rider assignment when a dish is marked ready. Dispatch picks the available rider with shortest configured simulated travel time while excluding riders with active assignments. Rider availability can be managed in Django admin. Times and distances are demonstration inputs.

**ETA Trust** computes a sequence: estimated food-ready time, rider arrival, whichever happens later as pickup, then an illustrative delivery leg. It returns a provisional range with a buffer and shows factors. There is no historical calibration or trained ML model yet, so Jyora does not claim accuracy or probability.

## Demo fee policy and payments

Checkout is recalculated from database prices: INR 5 demo platform fee, 5% food tax, restaurant delivery fee and optional `SAVE50` discount on food subtotals of at least INR 499. These are illustrative rules, not real policy. Cash on delivery and a labelled simulated online-payment option are supported. No payment credentials or card data are collected and no real transaction is made. Razorpay is not integrated.

## Configuration

Copy `.env.example` to `.env` and set a unique `SECRET_KEY` and `DEBUG=False` for a deployment. SQLite is the default. To use PostgreSQL, install `psycopg[binary]`, set `DATABASE_URL` using a `postgres://user:password@host:5432/database` URL, and configure the host's static/media deployment separately. Never commit `.env`.

## Current scope and next steps

Implemented now: customer registration/login, restaurant and dish search, menu browsing, single-restaurant cart replacement warning, quantity editing, address entry at checkout, server-side demo coupon/tax/total calculation, order creation/history/tracking, owner order transitions and availability toggles, admin entity management, FoodWise cost/value rows, Kitchensync simulated assignment, provisional ETA range, seed command and core automated tests.

Not implemented yet: persistent customer profile/address book, favorites UI, restaurant application review, owner restaurant profile and price editing UI, review collection, real location/GPS, polling updates, calibrated ETA history/model training, analytics charts, contact submission, real payment provider, image upload, PostgreSQL dependency/package verification, broad filter controls (price/rating/distance) and comprehensive automated coverage for every master-prompt scenario. Use Django admin for account/restaurant/rider setup. External assets are decorative Unsplash URLs with a CSS fallback color; internet is not required for ordering behavior.
