# **ChargeWise AI — Project Workflow and Technology Stack**

## **1\. Project Overview**

ChargeWise AI is a smart EV charging optimization web application. Users upload vehicle charging data, view analytics, generate a cost-efficient charging schedule, and use an AI agent to explain decisions or respond to simulated events such as charger failures and electricity price changes.

The application uses sample or historical data and simulated charging conditions. It does not require a connection to physical charging stations.

## **2\. Required Input Data**

### **CSV file**

Each row represents one vehicle's charging session.

| Field | Purpose |
| :---- | ----- |
| `vehicle_id` | Identifies the vehicle |
| `arrival_time` | Earliest charging time |
| `departure_time` | Deadline for departure |
| `energy_required_kwh` | Energy needed |
| `max_charging_power_kw` | Maximum charging rate |

### **App configuration**

* Number of available chargers
* Total station power limit (kW)
* Charging slot duration (e.g., 15 minutes)
* Electricity prices for each time slot
* Charger availability

## **3\. Complete Workflow**

### **Step 1 — Upload CSV**

The user uploads a CSV file. The backend validates the columns, data types, timestamps, and values.

**Tool:** React frontend \+ Python/FastAPI backend \+ Pandas.

### **Step 2 — Calculate Analytics**

The backend calculates the number of vehicles and sessions, total energy required, and other relevant statistics. Station configuration is used for capacity-related metrics.

**Tool:** Python \+ Pandas.

### **Step 3 — Display Dashboard**

The dashboard shows key metrics, electricity prices, station power limits, charging demand, and vehicles' arrival and departure times.

**Tool:** React \+ charting library.

### **Step 4 — Optimize Charging**

The optimizer assigns charging slots to vehicles while considering their energy requirements, deadlines, charging rates, charger availability, station power limits, and electricity prices.

The application also calculates a baseline schedule so users can compare cost and performance against the optimized schedule.

**Tool:** Google OR-Tools \+ Python.

### **Step 5 — Explain Results with AI**

Users can ask questions such as:

* Why is this vehicle scheduled at this time?
* Which vehicles are at risk of missing their deadlines?
* How can charging costs be reduced?

The AI agent uses the application's actual results and approved backend tools to answer.

**Tool:** NVIDIA Nemotron through the Nebius platform.

### **Step 6 — Simulate an Event**

The user selects an event, such as:

* A charger becoming unavailable.
* Electricity prices increasing during selected time slots.

The backend updates the simulated conditions.

**Tool:** React controls \+ FastAPI backend.

### **Step 7 — Re-optimize**

The AI agent can request a new schedule through an approved backend tool. OR-Tools recalculates the schedule using the updated conditions.

**Tool:** NVIDIA Nemotron for agent interaction; OR-Tools for scheduling.

### **Step 8 — Display Updated Results**

The dashboard refreshes the schedule, estimated cost, station power usage, missed energy targets, and vehicles at risk. The AI explains the changes.

**Tool:** FastAPI \+ OR-Tools \+ React \+ NVIDIA Nemotron.

## **4\. Technology Stack**

| Tool | Responsibility |
| ----- | ----- |
| React \+ Vite | Frontend and dashboard |
| Python \+ FastAPI | Backend API and application logic |
| Pandas | CSV validation and analytics |
| Google OR-Tools | Charging schedule optimization |
| NVIDIA Nemotron via Nebius | AI agent, tool calling, and explanations |
| Charting library | Dashboard graphs and schedule visualization |
| GitHub | Source code and project documentation |
| Cloud hosting | Public application deployment |

## **5\. Main Dashboard**

The dashboard displays:

* Total vehicles and charging sessions
* Total energy required
* Estimated charging cost
* Optimized vs. baseline cost
* Percentage of vehicles meeting energy targets
* Unserved energy
* Station power usage vs. power limit
* Charging schedule timeline
* Upcoming departures and vehicles at risk
* Charger status and electricity prices
* AI agent chat panel

## **6\. Important Implementation Rules**

* OR-Tools performs the actual scheduling calculations; the LLM does not replace the optimizer.
* Use clearly labeled simulated data for events and statuses.
* Do not claim cost savings unless the baseline and optimized results have actually been calculated.
* If the schedule is infeasible, show missed targets or unserved energy instead of claiming every vehicle can be fully charged.
* Keep the MVP simple: no database, physical chargers, or model training is required initially.

## **7\. Final Outcome**

A user uploads a CSV, sees the dashboard, generates an optimized charging schedule, asks the AI agent questions, simulates a change, and receives an updated schedule with refreshed metrics and explanations.

## 8. Scope retained from the earlier blueprint

Primary users are fleet, workplace, campus, and apartment charging operators. Start with one simulated station and 50 vehicles, then demonstrate a 100-session stress case. Multiple stations (3–5), persistent storage, real equipment, and distributed services are extensions. The existing files are documentation/data preparation; the application described above still needs implementation.

Keep the model roles separate: a time-series model predicts aggregate demand; Nemotron interprets requests and coordinates typed tools; OR-Tools calculates charging allocations; a deterministic validator checks every plan. NVIDIA Kumo-Forecast is the researched time-series candidate replacing the older Google TimesFM idea; see [forecasting and training data](docs/forecasting.md). Its deployment and forecast quality are not yet tested. A previous-day same-slot forecast is the initial comparison baseline; forecasting must not block the working scheduler/agent demo.

Use in-memory state and normal HTTP requests for the MVP. PostgreSQL, Redis Streams, and WebSockets can be added later if they solve an observed problem. Keep credentials on the backend. The planned React chart library can be Recharts; styling choices do not change the data/API contracts.

## 9. Scheduling and resilience acceptance criteria

- Use a rolling horizon of 15-minute slots. Power is in kW; energy is `power_kw * slot_hours * efficiency`; cost uses grid kWh times price per kWh.
- Enforce charger compatibility, one vehicle per connector, one connector per vehicle, per-vehicle/charger ratings, station caps, availability, and arrival/departure windows. Report explicit shortfall when targets cannot be met.
- First minimize unserved energy, then minimize energy cost. Peak-demand or carbon objectives are optional; declare units/weights and show supporting data before enabling them.
- Validate proposed schedules independently before activation. Keep the previous valid schedule visibly stale if replanning fails; never display an invalid plan as active.
- Include immutable event IDs and state/schedule versions. Ignore duplicate delivery, reject stale updates, and preserve energy already delivered when replanning.
- Supported demo events begin with `PRICE_CHANGED`, `CHARGER_FAILED`, and `CHARGER_RECOVERED`. Later events may include `EV_ARRIVED`, `SESSION_UPDATED`, and `SCHEDULE_UPDATED`.

Start with agent tools `get_state`, `get_schedule`, `optimize_schedule`, and `simulate_event`; `forecast_load` is optional. Explanations use actual tool results, rather than a second invented calculation. See [operating policy](docs/operating-policy.md).

## 10. Evaluation and demo

Run baseline and optimized schedules against the same inputs, prices, availability, capacity, event state, and horizon. Compare delivered energy alongside costs, so undercharging is never counted as savings. First-come-first-served charging is the baseline.

| Metric | Calculation |
| --- | --- |
| Charging energy cost | Sum of grid energy × slot price |
| Peak station demand | Maximum aggregate charging kW |
| Departure target success | Sessions meeting their target by departure / all sessions |
| Unserved energy | Sum of unmet battery kWh |
| Scheduler runtime | Elapsed optimizer execution time |
| Recovery time | Event receipt to validated replacement schedule |
| Estimated emissions, optional | Grid energy × matching geographic/time carbon intensity |

Demonstrate normal operation, a charger failure, a price spike, an infeasible target, and repeated delivery of the same event. Report measured results with scenario/seed and solver status; no savings have been measured yet. The demo story is baseline → optimize → ask Nemotron why → introduce outage → replan → compare results.

## 11. Build order and current inputs

1. Agree on [dataset schemas](docs/dataset-format.md) and API contracts; use the prepared demo fixtures.
2. Build upload validation, analytics, station settings, and baseline charging.
3. Implement OR-Tools, independent schedule checks, and metric comparison.
4. Build the dashboard and timeline around one complete scenario.
5. Integrate Nemotron through Nebius Token Factory and typed backend tools.
6. Add event handling, duplicate/stale update checks, and validated replanning.
7. Evaluate the time-series forecasting candidate if the core flow is reliable.
8. Deploy, complete actual run instructions, record the demo, and prepare submission evidence.

The [source registry](docs/data-sources.md) separates required demo inputs from optional solar/carbon/protocol features. GitHub holds only the small demo/reference datasets; larger future fine-tuning or LoRA corpora belong in cloud storage. See [storage](docs/storage.md), [team collaboration](CONTRIBUTING.md), and [verified hackathon checklist](docs/hackathon-rules.md).
