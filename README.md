# Hospital Capacity Planner

A decision-support prototype for hospital managers, developed by **Data Doctors** (UNSW × SAS Industry Project).

It uses a discrete-event simulation (DES) to explore how changes in admission demand, available beds and optional
patient-flow improvements could affect bed occupancy and waiting for a bed.

## Run locally

```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Python 3.11 or 3.12 is recommended.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit app (pages: Welcome, Historical Overview, Build a Scenario, Results) |
| `ui_components.py` | Styles and interface components |
| `simulation.py` | Discrete-event simulation model |
| `results_helpers.py` | Comparison runs and result summaries |
| `historical_summary.py`, `diagnosis_capacity.py` | Historical summaries |
| `calibration.npz`, `history_calendar.npz` | Model parameters and aggregated historical data |

## Important

- Results are hypothetical simulation outputs for planning discussion. They are not forecasts, not clinically
  validated and not specific to any hospital or ward.
- `calibration.npz` contains de-identified encounter-level values derived from the project data. Keep this
  repository and app private unless publication has been approved by the data provider. Raw data are not included.
