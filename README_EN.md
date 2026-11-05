# Axioma-H Engine (English summary)

This is a summary of the main [README.md](README.md), which is written in Spanish and is the authoritative version. The single source of all figures is [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md); this summary links to it instead of repeating its tables.

Axioma-H Engine is a rule-based control engine, designed as the first stage of a neuro-symbolic architecture, for passive atmospheric water harvesting nodes. From each node's telemetry (membrane impedance, matrix temperature, heat reserve and relative humidity), the engine decides whether to filter continuously, apply a resistive heat pulse to detach crystallized salt, reduce the flow, or stop extraction to protect the membrane and the ecosystem. A simulator compares this controller with a conventional fixed timer under five reference scenarios for Cabo de la Vela (La Guajira, Colombia).

It is developed by team AXIOMA for the Research Fundamentals course at the University of Antioquia (UdeA), Cycle 2.

## Links

| Resource | Link |
|---|---|
| Source code | https://github.com/crd10lop/axioma-h-engine |
| Deployed dashboard | https://axioma-h-dashboard.onrender.com |
| Deployed API (interactive docs) | https://axioma-h-api.onrender.com/docs |
| Versioned OpenAPI contract | [docs/api/openapi.json](docs/api/openapi.json) |
| Open reference data (CSV, JSON and Data Package) | [docs/datos/](docs/datos/README.md) |

## Research question

> To what extent does a neuro-symbolic control system, evaluated through simulation, improve water flow recovery and reduce membrane wear in an atmospheric water harvester, compared with a conventional timer-based control, as ambient salinity increases?

**Working hypothesis.** The neuro-symbolic control keeps a stable flow recovery and a lower accumulated degradation than the timer, and its advantage grows with salinity.

**Nature of the control.** The implemented engine is symbolic: explicit rules evaluated by priority, plus an explicit physical model. The "neural module" of the target architecture is not implemented and is left as future work. "Neuro-symbolic" describes the target architecture, not the current implementation. For compatibility, the API keeps the mode name neuro-symbolic (`NEURO_SIMBOLICO`, `modo_neuro_simbolico`) for the rule-based control. The dashboard uses a single visible name for the mode, "Control basado en reglas" (Rule-based control), with one note in the comparative simulation view stating the API code; in the result tables of the documentation, the mode is labelled "Control basado en reglas (modo neuro-simbólico)".

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

- **Backend (FastAPI, port 8000):** rule-based control engine (`backend/motor_reglas.py`, first stage of the neuro-symbolic architecture), physical model, comparative simulator, conjecture verification, community impact and robustness analyses (salinity sweep with several seeds, robustness of the answer to the assumed parameters, parameter sensitivity, fog flux calibration and uncertainty propagation), collector sizing and site profiles to transfer the model.
- **Frontend (Streamlit, port 8501):** presentation-only dashboard that consumes the API over HTTP. It has five views: research guide (question, current thesis, derived hypothesis, key assumptions with the measurement that would replace each one, and a reading guide by discipline), manual node evaluation, comparative simulation (with what would change each conjecture result), answer to the research question in four parts (wear, recovery, certainty and people supplied), and a hypothesis explorer (simulation with a custom pulse efficacy and site profile, and questions for Cycle 3 computed from the session data). API codes are shown in plain language.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Service health |
| POST | `/api/v1/nodo/evaluar` | Evaluates one node's telemetry |
| POST | `/api/v1/simulacion/ejecutar` | Runs the comparative simulation |
| POST | `/api/v1/analisis/barrido-salinidad` | Salinity sweep with mean and standard deviation over 1 to 5 seeds |
| POST | `/api/v1/analisis/sensibilidad` | Re-runs the simulation for several values of pulse efficacy or fog flux |
| POST | `/api/v1/analisis/incertidumbre` | Samples pulse efficacy and fog flux together and estimates the probability of validating each conjecture and of a recovery advantage for the rule-based control |
| POST | `/api/v1/analisis/robustez-respuesta` | Repeats the sweep with 3 fog fluxes by 3 pulse efficacies and reports where the recovery advantage crosses zero as a function of daily incrustation |
| POST | `/api/v1/analisis/robustez-desgaste` | Repeats the sweep with 2 fog fluxes by 3 fatigue-per-pulse values by 3 thermal degradation rates and reports the wear reduction of each combination |
| POST | `/api/v1/analisis/calibracion` | Calibrates the fog flux from a measured yield, using the temperature and daily amplitudes of a site profile; an unreachable yield returns 422 |
| POST | `/api/v1/analisis/dimensionamiento` | Collector area and nodes needed for a number of people, with the three reference fog fluxes |
| GET | `/api/v1/sitios` | Reference site profiles (Cabo de la Vela with the assumed flux and with the calibrated extremes) |

`POST /api/v1/simulacion/ejecutar` also accepts an optional `sitio` profile (name, maximum fog flux, mean temperature and daily temperature and humidity amplitudes) and an optional `eficacia_maxima_pulso`. Without them, the Cabo de la Vela values are used and results do not change. The response reports the values used in `parametros_usados`.

## Installation and local use

Requires Python 3.11 or later. From the project root:

```bash
python -m venv venv
# Windows (PowerShell):  .\venv\Scripts\activate
# Linux and macOS:       source venv/bin/activate
pip install -r requirements.txt
```

On Linux and macOS you may need `python3` instead of `python`.

Run the backend and the dashboard in two terminals:

```bash
uvicorn backend.main:app --reload --port 8000
streamlit run frontend/app.py
```

Everything runs locally without an internet connection; the dashboard connects to `http://127.0.0.1:8000` by default. The reference data, the Data Package descriptor and the OpenAPI contract can be regenerated without the API, and `--comprobar` checks that they match the current code:

```bash
python scripts/generar_resultados_referencia.py
```

Tests (no network access):

```bash
pip install -r requirements-dev.txt
pytest --cov --cov-report=term-missing
```

## Deployment

The API and the dashboard are deployed on **Render** (free plan) as two web services defined in `render.yaml` and built from the `main` branch. Each push to `main` runs the CI workflow (tests, coverage and SonarQube Cloud analysis), and Render deploys both services only when all checks pass. The automated verification script (`python scripts/verificar_despliegue.py`) runs 29 checks against the published services; the latest recorded run is in section 4.3 of docs/05. Details are in [docs/05_Despliegue_y_Operacion_AxiomaH.md](docs/05_Despliegue_y_Operacion_AxiomaH.md) (in Spanish).

## Results

All figures come from model runs; their single source is [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sections 5 to 8 (in Spanish). With 24 h, 85 % initial humidity and the evaluated ranges of fog flux and pulse efficacy:

- **Wear.** The rule-based control reduces membrane degradation by 73.3 % to 100 % compared with the timer at all 54 points of the nine combinations of fog flux and pulse efficacy (section 8.8). With half and double the assumed fatigue per pulse and thermal degradation, it degrades less at all 108 points of 18 combinations, with a reduction of 61.5 % to 100 % (section 8.11).
- **Recovery.** Its advantage depends on daily incrustation, not on the salt load per litre: the crossing lies between 1632.9 and 1839.2 Ohm/day with seed 42 (1682.1 to 1866.6 with seeds 1 to 3), while the salt load per litre at the crossing ranges from 50.3 to 190.9 Ohm per L/m². The two levels between which each crossing is interpolated are 617 to 1165 Ohm/day apart, more than that range: the sweep cannot tell the crossings of the combinations apart, and each one lies somewhere between 1171 and 2365 Ohm/day (section 8.8).
- **With literature-like fog.** With the minimum calibrated flux, 0.49 L/m²/h, daily incrustation never exceeds 659 Ohm/day and the timer recovers more at every level with pulses; with the calibrated flux, the rule-based control recovers more in only 3 of 62 uncertainty samples (sections 8.7 and 8.8).
- **Conjectures.** Conjectures 1 and 2 depend on pulse efficacy, which must be measured (0.94 and 0.97 would validate them, section 6.2); Conjecture 3 is not validated with the calibrated flux (section 8.6).
- **People.** Supplying 50 people with 20 L per day would take 32 nodes of 1 m² with the assumed flux and 100 to 332 with the calibrated flux, in line with the 100 to 333 m² from the literature (section 7.7).

The answer is conditional: the wear reduction is robust, and the recovery advantage appears only above a daily incrustation of about 1633 to 1867 Ohm/day. This leads to the derived hypothesis H1-Cycle 3 (docs/04, section 8.9).

The 33 % cap comes from the team's formulation of Conjecture 3 (narrative of Cycle 1, "El Axioma del Silencio"). It is neither documented Wayuu knowledge nor a criterion taken from the ecological literature, and it must be validated with the communities. A four-step co-creation protocol is proposed for Cycle 3: prior consultation, community validation of the cap and the ecological pause, translation of the interface with Wayuu translators, and governance rules for the device and the data (docs/01, section 2.7).

## Limitations

- Results come from a simulated model, not from field measurements.
- Pulse efficacy (0.90) and the other physical parameters (fog flux, incrustation rates, heat capacity, energy use and recharge, membrane degradation) are order-of-magnitude assumptions pending experimental validation.
- The status of Conjectures 1 and 2 changes with pulse efficacy; measuring it is the priority before declaring either validated or refuted.
- The reference climate uses idealized daily cycles with Gaussian noise.
- The assumed fog flux is optimistic compared with the literature (see references).
- The available site profiles are only for Cabo de la Vela, because the project has no sourced climate data for other sites.
- This is an analytical proof of concept, roughly TRL 2-3, with no physical prototype. Prior consultation with Wayuu communities (ILO Convention 169, Colombian Law 21 of 1991) is required before any pilot in their territory and has not been carried out.

## Version history

| Version | Content |
|---|---|
| 0.1.0 | Rule-based control engine, comparative simulation against the fixed timer, verification of the three conjectures, Streamlit dashboard and deployment on Render. |
| 0.2.0 | Robustness analyses (salinity sweep with several seeds and sensitivity), causes of non-validation, timer with ecological cap, community impact, conservative human supervision (REGLA_06) and uncertainty propagation with the calibrated fog flux. |
| 0.3.0 | Robustness of the answer to fog flux and pulse efficacy, daily incrustation and recovery crossing in the sweep, recovery advantage in the uncertainty analysis, collector sizing, site profile and pulse efficacy in the simulation, `parametros_usados` and `GET /api/v1/sitios`. |
| 0.4.0 | Robustness of the wear reduction to fatigue per pulse and thermal degradation, interpolated levels and separation of the recovery crossing, and fog flux calibration through the API with the site profile. Default model results do not change. |

The 0.2.0 features were added incrementally while the service still reported 0.1.0; the version number was updated when the set was closed. The five-view dashboard and the interoperable data (Data Package and versioned OpenAPI) were added on top of API 0.3.0, without changes to the API.

## Documentation

The documents in `docs/` are numbered in reading order (all in Spanish):

1. [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md): research question, conjectures, variables, study perspectives, scope and milestones.
2. [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md): API specification and implementation status.
3. [03_Funcionamiento_General_AxiomaH.md](docs/03_Funcionamiento_General_AxiomaH.md): plain-language explanation of the application and the dashboard.
4. [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md): rules, equations, results and critical reading of the conjectures.
5. [05_Despliegue_y_Operacion_AxiomaH.md](docs/05_Despliegue_y_Operacion_AxiomaH.md): deployment on Render, CI, verification and integration with other systems (curl, pandas, Data Package validation and real sensors, section 7).
6. [06_Referencias_y_Trazabilidad_AxiomaH.md](docs/06_Referencias_y_Trazabilidad_AxiomaH.md): third-party software, scientific sources and parameter traceability.

The reference data and its field dictionary are in [docs/datos/](docs/datos/README.md).

## References

- Third-party software, licenses, the scientific sources and the traceability of every model parameter: [docs/06_Referencias_y_Trazabilidad_AxiomaH.md](docs/06_Referencias_y_Trazabilidad_AxiomaH.md) (in Spanish).
- Klemm, O., Schemenauer, R. S., Lummerich, A., et al. (2012). Fog as a fresh-water resource: overview and perspectives. *Ambio*, 41, 221-234. https://doi.org/10.1007/s13280-012-0247-8
- Howard, G., Bartram, J., Williams, A., Overbo, A., Fuente, D. and Geere, J.-A. (2020). *Domestic water quantity, service level and health* (2nd ed.). World Health Organization. https://www.who.int/publications/i/item/9789240015241
- Sphere Association (2018). *The Sphere Handbook: Humanitarian Charter and Minimum Standards in Humanitarian Response* (4th ed.), water supply standard 2.1. https://spherestandards.org
- Model, equations, sensitivity analyses and critical reading of the conjectures: [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) (in Spanish).

The project is distributed under the MIT license (`LICENSE` file).
