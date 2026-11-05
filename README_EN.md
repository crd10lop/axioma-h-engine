# Axioma-H Engine (English summary)

This is a summary of the main [README.md](README.md), which is written in Spanish and is the authoritative version. All figures below are copied from it.

Axioma-H Engine is a rule-based control engine, designed as the first stage of a neuro-symbolic architecture, for passive atmospheric water harvesting nodes. From each node's telemetry (membrane impedance, matrix temperature, heat reserve and relative humidity), the engine decides whether to filter continuously, apply a resistive heat pulse to detach crystallized salt, reduce the flow, or stop extraction to protect the membrane and the ecosystem. A simulator compares this controller with a conventional fixed timer under five reference scenarios for Cabo de la Vela (La Guajira, Colombia).

It is developed by team AXIOMA for the Research Fundamentals course at the University of Antioquia (UdeA), Cycle 2.

## Links

| Resource | Link |
|---|---|
| Source code | https://github.com/crd10lop/axioma-h-engine |
| Deployed dashboard | https://axioma-h-dashboard.onrender.com |
| Deployed API (interactive docs) | https://axioma-h-api.onrender.com/docs |
| Open reference data (CSV and JSON) | [docs/datos/](docs/datos/README.md) |

## Research question

> To what extent does a neuro-symbolic control system, evaluated through simulation, improve water flow recovery and reduce membrane wear in an atmospheric water harvester, compared with a conventional timer-based control, as ambient salinity increases?

**Working hypothesis.** The neuro-symbolic control keeps a stable flow recovery and a lower accumulated degradation than the timer, and its advantage grows with salinity.

**Nature of the control.** The implemented engine is symbolic: explicit rules evaluated by priority, plus an explicit physical model. The "neural module" of the target architecture is not implemented and is left as future work. "Neuro-symbolic" describes the target architecture, not the current implementation. For compatibility, the API and the dashboard keep the mode name neuro-symbolic (`NEURO_SIMBOLICO`, `modo_neuro_simbolico`) for the rule-based control; in the tables below, "Neuro-symbolic" refers to that mode.

## Control rules

Rules are evaluated in this order and the first one that matches decides. Flow is expressed as a percentage of the ecological cap: the system never extracts more than 33 % of the available fog.

| Priority | Rule | Condition | Action | Flow |
|---|---|---|---|---|
| 1 | REGLA_01 | Temperature >= 45 °C | Emergency cut-off | 0 % |
| 2 | REGLA_02 | Relative humidity < 30 % | Ecological pause | 0 % |
| 3 | REGLA_06 | Operator override: `SUSPENDER_EXTRACCION`, or `INHIBIR_PULSO` with impedance > 1500 Ohm | Manual suspension, or reduce flow without pulse | 0 % or 50 % |
| 4 | REGLA_04 | Reserve < 30 % and impedance > 1500 Ohm | Reduce flow, no pulse | 50 % |
| 5 | REGLA_03 | Impedance > 1500 Ohm and reserve >= 30 % | Resistive pulse to 44 °C for 90 s | 80 % |
| 6 | REGLA_05 | None of the above | Continuous passive filtration | 100 % |

REGLA_06 is human supervision, set with the optional `anulacion_manual` field of `POST /api/v1/nodo/evaluar` (`NINGUNA` by default). The operator can only be more conservative than the engine: it can never force extraction or pulses, and REGLA_01 and REGLA_02 take precedence. It does not apply to the fixed timer mode or to the simulation.

## Architecture

Two services run separately:

- **Backend (FastAPI, port 8000):** rule-based control engine (`backend/motor_reglas.py`, first stage of the neuro-symbolic architecture), physical model, comparative simulator, conjecture verification, community impact and robustness analyses (salinity sweep with several seeds, parameter sensitivity, fog flux calibration and uncertainty propagation).
- **Frontend (Streamlit, port 8501):** dashboard that consumes the API over HTTP. It has four views: research guide, manual node evaluation, comparative simulation, and answer to the research question.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Service health |
| POST | `/api/v1/nodo/evaluar` | Evaluates one node's telemetry |
| POST | `/api/v1/simulacion/ejecutar` | Runs the comparative simulation |
| POST | `/api/v1/analisis/barrido-salinidad` | Salinity sweep with mean and standard deviation over 1 to 5 seeds |
| POST | `/api/v1/analisis/sensibilidad` | Re-runs the simulation for several values of pulse efficacy or fog flux |
| POST | `/api/v1/analisis/incertidumbre` | Samples pulse efficacy and fog flux together and estimates the probability of validating each conjecture |

## Installation and local use

Requires Python 3.11 or later. On Windows, from the project root in PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Run the backend and the dashboard in two terminals:

```powershell
uvicorn backend.main:app --reload --port 8000
streamlit run frontend/app.py
```

Everything runs locally without an internet connection; the dashboard connects to `http://127.0.0.1:8000` by default. The reference data can also be regenerated without the API:

```powershell
python scripts/generar_resultados_referencia.py
```

Tests (no network access):

```powershell
pip install -r requirements-dev.txt
pytest --cov --cov-report=term-missing
```

## Deployment

The API and the dashboard are deployed on **Render** (free plan) as two web services defined in `render.yaml` and built from the `main` branch. Each push to `main` runs the CI workflow (tests, coverage and SonarQube Cloud analysis), and Render deploys both services only when all checks pass. The automated verification script (`python scripts/verificar_despliegue.py`) runs 22 checks against the published services; the latest recorded run is in section 4.3 of docs/05. Details are in [docs/05_Despliegue_y_Operacion_AxiomaH.md](docs/05_Despliegue_y_Operacion_AxiomaH.md) (in Spanish).

## Results

All runs: 24 h starting at 18:00, 5 min steps, 8 nodes, seed 42, high salinization rate (ALTA), unmodified parameters (pulse efficacy 0.90, regeneration criterion 1100 Ohm).

### PRD reference run (salt storm with extreme heat, initial humidity 45 %)

| Metric | Neuro-symbolic | Fixed timer |
|---|---|---|
| Water collected (L) | 81.65 | 120.41 |
| Heat pulses | 19 | 88 |
| Energy consumed (Wh) | 323.2 | 1065.1 |
| Final integrity (%) | 99.95 | 97.09 |
| Ecological violations | 0 | 8 |

None of the three conjectures is validated in this run: flow recovery is 88.81 % (threshold 90 %), regeneration time is 22 263 s (threshold 120 s, 0 of 19 pulses regenerated), and night yield is 5.95 L/m²/night (threshold 12).

### Conjecture status

- **C3 (territorial knowledge):** the rule-based control recorded no ecological violations in any scenario. It is validated in four scenarios with 85 % initial humidity. With 45 % it is not, because the atmospheric resource is insufficient: night yield stays between 4 and 6 L/m²/night, and the timer does not reach 12 L/m²/night either.
- **C1 (efficiency):** energy savings meet the threshold in almost all cases, but flow recovery after the pulse stays below 90 %.
- **C2 (self-repair):** the absence of thermal degradation holds in the model (0 % in all ten scenarios); dissolution efficacy cannot be verified by simulation because it depends on pulse efficacy, an assumed parameter.
- **Required efficacy:** validating C1 requires a 90 s pulse at 44 °C to remove at least 78 % of the salt crust (`eta_max` >= 0.94); validating C2 requires at least 81 % (`eta_max` >= 0.97). This is the priority laboratory measurement for the next cycle.

### Salinity sweep (initial humidity 85 %)

| Salt load (Ohm per L/m²) | Recovery neuro / timer (%) | Degradation neuro / timer (%) |
|---|---|---|
| 20 | 88.85 / 95.84 | 0.020 / 2.071 |
| 40 | 88.83 / 91.83 | 0.052 / 2.071 |
| 60 | 88.80 / 88.02 | 0.082 / 2.117 |
| 80 | 88.78 / 84.45 | 0.115 / 2.427 |
| 120 | 88.02 / 78.02 | 0.408 / 3.070 |
| 240 | 85.92 / 63.21 | 1.073 / 4.117 |

The rule-based control reduces accumulated degradation by 74 % to 99 % at every level. Its recovery stays stable, while the timer's falls with salinity: the timer recovers more at low salinity, because it cleans nearly clean membranes, and the neuro-symbolic control overtakes it from 60 Ohm per L/m².

### Ecological cap versus control logic

A reference timer with the same 0.33 cap separates the two causes of the water gap:

| Run | Neuro-symbolic (L) | Timer 0.45 (L) | Timer 0.33 (L) | Gap due to the cap |
|---|---|---|---|---|
| Salt storm with extreme heat, humidity 45 % | 81.7 | 120.4 | 91.8 | 73.9 % |
| Normal day, humidity 85 % | 254.6 | 340.4 | 266.1 | 86.6 % |

Across the five scenarios, the cap explains 69.8 % to 89.8 % of the gap with 45 % initial humidity and 76.2 % to 90.8 % with 85 %. The lower yield of the neuro-symbolic control is mostly the cost of the ecological limit, not of the control logic.

### Fog flux calibration and parameter uncertainty

The assumed fog flux (6.0 L/m²/h) yields 31.8 L/m² per day on a normal day with 85 % humidity, versus 3 to 10 L/m² per day in operational projects (Klemm et al., 2012). An inverse calibration by bisection finds the fluxes that reproduce that range: 0.49 to 1.83 L/m²/h. The model default does not change; the calibrated range is used only in the uncertainty analysis. With the calibrated flux, C3 is not validated on a normal day with 85 % humidity.

`POST /api/v1/analisis/incertidumbre` samples pulse efficacy (0.80 to 1.00) and the calibrated flux together. With 20 samples, 85 % initial humidity and a high salinization rate, the probability of validating C1 ranges from 0.00 to 0.15, C2 from 0.00 to 0.10 and C3 is 0.00 in all five scenarios. With less fog there is less salt and many runs apply no pulse, so C1 and C2 lack data rather than being refuted. The lower membrane degradation of the neuro-symbolic control holds across all samples (95.7 % to 100 % reduction between the 5th and 95th percentiles). Details are in docs/04, sections 8.6 and 8.7.

### Estimated community impact

Each simulation converts the collected water into people supplied (`impacto_comunitario`), using the WHO basic access level (20 L per person per day, Howard et al., 2020) and the Sphere humanitarian minimum (15 L per person per day, standard 2.1). It is an informative indicator and does not affect validation.

- With the assumed fog flux and 85 % initial humidity, the 8 m² network would supply about 12 people at the basic access level on a normal day (12.7), and 7.5 to 12.7 depending on the scenario. With 45 %, 2.0 to 4.1.
- The simulated yield at 85 % (18.7 to 31.8 L/m² per day) exceeds the 3 to 10 L/m² per day reported for operational projects (Klemm et al., 2012). At those yields, 2 to 6.7 m² of collector per person would be needed.
- The ecological cap reduces the number of people supplied compared with the timer: 2.8 to 4.3 fewer with 85 % and 1.1 to 2.2 fewer with 45 %.

The 33 % cap comes from the team's formulation of Conjecture 3 (narrative of Cycle 1, "El Axioma del Silencio"). It is neither documented Wayuu knowledge nor a criterion taken from the ecological literature, and it must be validated with the communities. A four-step co-creation protocol is proposed for Cycle 3: prior consultation, community validation of the cap and the ecological pause, translation of the interface with Wayuu translators, and governance rules for the device and the data (docs/01, section 2.7).

## Limitations

- Results come from a simulated model, not from field measurements.
- Pulse efficacy (0.90) and the other physical parameters (fog flux, incrustation rates, heat capacity, energy use and recharge, membrane degradation) are order-of-magnitude assumptions pending experimental validation.
- The status of Conjectures 1 and 2 changes with pulse efficacy; measuring it is the priority before declaring either validated or refuted.
- The reference climate uses idealized daily cycles with Gaussian noise.
- The assumed fog flux is optimistic compared with the literature (see references).
- This is an analytical proof of concept, roughly TRL 2-3, with no physical prototype. Prior consultation with Wayuu communities (ILO Convention 169, Colombian Law 21 of 1991) is required before any pilot in their territory and has not been carried out.

## Version history

| Version | Content |
|---|---|
| 0.1.0 | Rule-based control engine, comparative simulation against the fixed timer, verification of the three conjectures, Streamlit dashboard and deployment on Render. |
| 0.2.0 | Robustness analyses (salinity sweep with several seeds and sensitivity), causes of non-validation, timer with ecological cap, community impact, conservative human supervision (REGLA_06) and uncertainty propagation with the calibrated fog flux. |

The 0.2.0 features were added incrementally while the service still reported 0.1.0; the version number was updated when the set was closed.

## Documentation

The documents in `docs/` are numbered in reading order (all in Spanish):

1. [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md): research question, conjectures, variables, study perspectives, scope and milestones.
2. [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md): API specification and implementation status.
3. [03_Funcionamiento_General_AxiomaH.md](docs/03_Funcionamiento_General_AxiomaH.md): plain-language explanation of the application and the dashboard.
4. [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md): rules, equations, results and critical reading of the conjectures.
5. [05_Despliegue_y_Operacion_AxiomaH.md](docs/05_Despliegue_y_Operacion_AxiomaH.md): deployment on Render, CI and verification.
6. [06_Referencias_y_Trazabilidad_AxiomaH.md](docs/06_Referencias_y_Trazabilidad_AxiomaH.md): third-party software, scientific source and parameter traceability.

The reference data and its field dictionary are in [docs/datos/](docs/datos/README.md).

## References

- Third-party software, licenses, the scientific sources and the traceability of every model parameter: [docs/06_Referencias_y_Trazabilidad_AxiomaH.md](docs/06_Referencias_y_Trazabilidad_AxiomaH.md) (in Spanish).
- Klemm, O., Schemenauer, R. S., Lummerich, A., et al. (2012). Fog as a fresh-water resource: overview and perspectives. *Ambio*, 41, 221-234. https://doi.org/10.1007/s13280-012-0247-8
- Howard, G., Bartram, J., Williams, A., Overbo, A., Fuente, D. and Geere, J.-A. (2020). *Domestic water quantity, service level and health* (2nd ed.). World Health Organization. https://www.who.int/publications/i/item/9789240015241
- Sphere Association (2018). *The Sphere Handbook: Humanitarian Charter and Minimum Standards in Humanitarian Response* (4th ed.), water supply standard 2.1. https://spherestandards.org
- Model, equations, sensitivity analyses and critical reading of the conjectures: [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) (in Spanish).

The project is distributed under the MIT license (`LICENSE` file).
