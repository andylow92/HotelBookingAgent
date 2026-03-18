# TravelNeg API Manual Testing Guide

This README explains how to manually test the main tools in the project from your terminal.

## Prerequisites

Make sure you are in the project root and your Python virtual environment is activated.

### Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

If you already have a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

If you are missing packages during testing, install them as needed, for example:

```bash
pip install httpx pydantic pytest python-dotenv
```

## Environment variables

Some tools require API keys.

For the weather client, export your weather API key before testing:

```bash
export WEATHER_API_KEY=your_key_here
```

You can confirm it is set with:

```bash
echo $WEATHER_API_KEY
```

---

## 1. Test the Weather Client

Use this to verify the weather integration and daily forecast parsing.

```bash
python -c "
import asyncio
from travelneg.consumer_agent.weather_client import fetch_weather

async def main():
    result = await fetch_weather('Berlin')
    print('Summary:', result.summary)
    for day, fc in result.daily.items():
        print(f'  {day}: {fc.condition}, {fc.temp}°C, humidity {fc.humidity}%')

asyncio.run(main())
"
```

### Try other cities

You can swap `'Berlin'` for:

- `'Madrid'`
- `'Paris'`
- `'Tokyo'`

### Expected result

You should see:

- A summary line
- Several daily forecast rows
- Temperature and humidity values for each day

### Common issues

If you see `ModuleNotFoundError`, install the missing package in your active environment:

```bash
pip install httpx pydantic
```

If you see an API-related error, verify that `WEATHER_API_KEY` is correctly set.

---

## 2. Test Geocoding and Distance Calculation

Use this to verify address lookup and distance calculations.

```bash
python -c "
import asyncio
from travelneg.shared.geocoding import geocode, haversine

async def main():
    alex = await geocode('Alexanderplatz, Berlin')
    print(f'Alexanderplatz: {alex}')

    hbf = await geocode('Berlin Hauptbahnhof')
    print(f'Hauptbahnhof:   {hbf}')

    if alex and hbf:
        print(f'Distance: {haversine(alex, hbf):.2f} km')

asyncio.run(main())
"
```

### Notes

Nominatim has a rate limit of about 1 request per second, so this test usually takes around 2 seconds.

### Expected result

You should see:

- Coordinates or location objects for both places
- A computed distance in kilometers

---

## 3. Test the Scorer

Use this to check how hotel options are scored, ranked, and tagged.

```bash
python -c "
from travelneg.provider_agent.scorer import score_option, rank_and_tag, generate_negotiation_note
from travelneg.shared.domain_config import get_domain
from travelneg.shared.models import Weights

domain = get_domain('hotels')
w = Weights(price=0.25, location=0.30, rating=0.20, flexibility=0.15, match=0.10)

options = []
for name, price, rating, dist, flex, feats in [
    ('Motel One',       89,  4.3, 0.3, 'free',    ['wifi', 'breakfast']),
    ('Generator',       62,  3.6, 1.2, 'none',    ['wifi']),
    ('Hotel Indigo',   142,  4.8, 0.5, 'free',    ['wifi', 'breakfast', 'pool']),
    ('Holiday Inn',    110,  4.0, 2.0, 'partial', ['wifi', 'breakfast']),
]:
    options.append(score_option(
        option_id=name.lower().replace(' ','_'),
        name=name, price=price, rating=rating, distance_km=dist,
        flexibility=flex, matched_features=feats,
        desired_features=['wifi', 'breakfast', 'pool'],
        weights=w, max_budget=150, domain=domain,
    ))

ranked = rank_and_tag(options, top_n=3)
for o in ranked:
    print(f'{o.tag:15s} {o.name:25s} score={o.total_score:.4f}  €{o.price}  {o.rating}★  {o.distance_km}km')
    b = o.score_breakdown
    print(f'                {"":25s} price={b.price:.2f} loc={b.location:.2f} rat={b.rating:.2f} flex={b.flexibility:.2f} match={b.match:.2f}')

print()
print('Negotiation note:')
print(generate_negotiation_note(ranked, max_budget=150))
"
```

### Expected result

You should see:

- Ranked hotel options
- A score breakdown for each result
- A generated negotiation note at the end

This is a good sanity check for the scoring logic.

---

## 4. Test Re-weighting in the Negotiation Loop

This is one of the most important demos in the project.

It shows that with the same hotel options, changing the user preference weights can change the winning result.

```bash
python -c "
from travelneg.provider_agent.scorer import score_option, rank_and_tag
from travelneg.shared.domain_config import get_domain
from travelneg.shared.models import Weights

domain = get_domain('hotels')
data = [
    ('Motel One',     89, 4.3, 0.3, 'free',    ['wifi','breakfast']),
    ('Generator',     62, 3.6, 1.2, 'none',    ['wifi']),
    ('Hotel Indigo', 142, 4.8, 0.5, 'free',    ['wifi','breakfast','pool']),
]
desired = ['wifi','breakfast','pool']

for label, w in [
    ('Balanced',        Weights()),
    ('Cheapest',        Weights(price=0.55, location=0.10, rating=0.15, flexibility=0.10, match=0.10)),
    ('Best location',   Weights(price=0.10, location=0.45, rating=0.20, flexibility=0.10, match=0.15)),
    ('Need flexibility',Weights(price=0.15, location=0.15, rating=0.15, flexibility=0.40, match=0.15)),
]:
    opts = [score_option(
        option_id=n.lower().replace(' ','_'), name=n, price=p, rating=r,
        distance_km=d, flexibility=f, matched_features=mf,
        desired_features=desired, weights=w, max_budget=150, domain=domain,
    ) for n, p, r, d, f, mf in data]
    ranked = rank_and_tag(opts, top_n=1)
    print(f'{label:20s} → Winner: {ranked[0].name} (score={ranked[0].total_score:.4f})')
"
```

### Why this matters

This is the clearest demonstration of the negotiation loop:

- Same options
- Different priorities
- Different winner

This is likely the best demo moment for a presentation.

---

## 5. Run the Full Test Suite

To run all automated tests:

```bash
python -m pytest tests/ -v
```

### Expected result

You should see pytest discover and run all tests under `tests/` with verbose output.

---

## Recommended Testing Flow

For a quick manual validation, run the tests in this order:

1. Weather client
2. Geocoding + distance
3. Scorer
4. Re-weighting demo
5. Full pytest suite

This gives you both:

- Functional API/tool checks
- A good end-to-end demo story for the team

---

## Troubleshooting

### Missing package errors

If you get errors like:

```bash
ModuleNotFoundError: No module named 'httpx'
```

install the package with:

```bash
pip install httpx
```

Another common package:

```bash
pip install pydantic
```

To save all currently installed dependencies:

```bash
pip freeze > requirements.txt
```

### Virtual environment issues

Make sure the environment is active:

```bash
source .venv/bin/activate
which python
```

The Python path should point to `.venv`.

### API key issues

If the weather client fails, re-check:

```bash
echo $WEATHER_API_KEY
```

---

## Optional `.gitignore`

If the repo does not already have one, you can create a basic Python `.gitignore` from terminal:

```bash
cat > .gitignore <<'EOF'
# Virtual environment
.venv/
venv/
env/

# Python cache
__pycache__/
*.py[cod]
*$py.class

# Build / packaging
build/
dist/
*.egg-info/
.eggs/

# Logs
*.log

# Environment variables
.env

# IDE files
.vscode/
.idea/

# Jupyter
.ipynb_checkpoints/

# OS files
.DS_Store
Thumbs.db
EOF
```

---

## Summary

This project can be manually tested from terminal by validating:

- Weather fetching
- Geocoding and distance computation
- Hotel scoring and ranking
- Preference re-weighting behavior
- Full automated tests

Use the re-weighting example as the main demo, since it best highlights the value of the negotiation logic.
