Viewed main.py:1-9

Step-by-step to run the project:

### 1. Set up .env
cp .env.example .env

Then edit .env and add your Groq API key:
GROQ_API_KEY=gsk_your_key_here


### 2. Install dependencies
pip install -r requirements.txt


### 3. Run the server
python -m gridwise

Server starts at http://localhost:8000

---

### 4. Test it — send a request
curl -s -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "test-01",
    "operator_notes": [
      "Solar output will drop to about 20% from 1 PM to 3 PM.",
      "Do not charge the battery between 2 PM and 4 PM.",
      "The cafeteria menu changes tomorrow."
    ],
    "hours": [
      {"hour": 0, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
      {"hour": 1, "demand_kwh": 45, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
      {"hour": 2, "demand_kwh": 42, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
      {"hour": 3, "demand_kwh": 40, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
      {"hour": 4, "demand_kwh": 41, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
      {"hour": 5, "demand_kwh": 43, "solar_kwh": 0, "tariff_bdt_per_kwh": 8},
      {"hour": 6, "demand_kwh": 60, "solar_kwh": 10, "tariff_bdt_per_kwh": 10},
      {"hour": 7, "demand_kwh": 75, "solar_kwh": 30, "tariff_bdt_per_kwh": 10},
      {"hour": 8, "demand_kwh": 90, "solar_kwh": 60, "tariff_bdt_per_kwh": 12},
      {"hour": 9, "demand_kwh": 100, "solar_kwh": 90, "tariff_bdt_per_kwh": 12},
      {"hour": 10, "demand_kwh": 110, "solar_kwh": 110, "tariff_bdt_per_kwh": 15},
      {"hour": 11, "demand_kwh": 115, "solar_kwh": 120, "tariff_bdt_per_kwh": 15},
      {"hour": 12, "demand_kwh": 120, "solar_kwh": 125, "tariff_bdt_per_kwh": 15},
      {"hour": 13, "demand_kwh": 118, "solar_kwh": 120, "tariff_bdt_per_kwh": 18},
      {"hour": 14, "demand_kwh": 115, "solar_kwh": 100, "tariff_bdt_per_kwh": 18},
      {"hour": 15, "demand_kwh": 110, "solar_kwh": 80, "tariff_bdt_per_kwh": 18},
      {"hour": 16, "demand_kwh": 105, "solar_kwh": 50, "tariff_bdt_per_kwh": 20},
      {"hour": 17, "demand_kwh": 100, "solar_kwh": 20, "tariff_bdt_per_kwh": 20},
      {"hour": 18, "demand_kwh": 95, "solar_kwh": 5, "tariff_bdt_per_kwh": 20},
      {"hour": 19, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 18},
      {"hour": 20, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 15},
      {"hour": 21, "demand_kwh": 75, "solar_kwh": 0, "tariff_bdt_per_kwh": 12},
      {"hour": 22, "demand_kwh": 60, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
      {"hour": 23, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 8}
    ],
    "battery": {
      "capacity_kwh": 500,
      "initial_energy_kwh": 200,
      "minimum_energy_kwh": 50,
      "max_charge_kwh_per_hour": 100,
      "max_discharge_kwh_per_hour": 100
    }
  }' | python -m json.tool


### 5. Health check
curl http://localhost:8000/health


---
