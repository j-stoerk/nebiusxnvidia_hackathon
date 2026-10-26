# Pretrained models: measured results

Actually executed on CPU on 26 October 2026, using public checkpoints and no inference API. This follow-up reuses 37 locally held-out days from August–September 2019; see the [fixed follow-up protocol](foundation-forecasting.md) and [machine-readable results](foundation-forecast-results.json). These are exploratory observations; unknown pretraining overlap prevents a clean out-of-distribution claim.

| Forecast | Price MAE, EUR/MWh | Energy-only scenario EUR/day | With illustrative demand, EUR/day |
| --- | ---: | ---: | ---: |
| Yesterday repeat | 7.607 | 3.3640 | 138.9204 |
| Last week repeat | 7.833 | 3.3918 | 138.9162 |
| Ridge baseline | 7.042 | 3.3353 | 138.9116 |
| TimesFM 2.5 200M | 5.720 | 3.3377 | **138.9092** |
| Chronos-Bolt Tiny 9M | 5.315 | 3.3393 | 138.9096 |
| Chronos-Bolt Small 48M | **4.988** | 3.3395 | 138.9095 |
| Perfect-price oracle | — | **3.3141** | 138.9059 |

The forecasting error improvement is substantial: Chronos Small improves on ridge by **29.2%** and yesterday-repeat by **34.4%**. Forecast accuracy does not directly determine charging cost: ridge remains best among the forecasts for energy-only cost, while TimesFM is best with the illustrative demand component, improving on ridge by about **EUR0.0025 per four-van scenario-day**. All 518 paired scenario/model/tariff solves passed independent checks, met every energy target and finished with proven cost optimality against that run's supplied prices. No incomplete runs were dropped.

Each replay uses the synthetic four-van roster, declared fixed plugs/SoC/efficiency, actual held-out wholesale prices, and either zero demand rate or EUR15.20/kW/month with a fresh zero prior peak for that independent day. These are partial-period **scenario calculations**, not an observed German depot bill, recurring monthly savings or an annual return. Real retail prices and site load are absent. Already published prices should be used directly instead of being predicted.

The native nominal 80% intervals cover **76.6% (TimesFM), 77.5% (Tiny), 77.4% (Small)** of held-out hourly prices. Mean pinball losses at 0.1/0.5/0.9 are in the JSON. These intervals are uncalibrated; they do not establish any 95% vehicle-readiness probability. Seven-day bootstrap intervals for cost differences against yesterday-repeat are also recorded; the energy-only foundation-model intervals include zero. No multiplicity correction was applied.

Inference for all 37 contexts took approximately **3.45 s (TimesFM), 1.05 s (Tiny), 6.96 s (Small)** on this CPU setup. Loading/downloading is separate and recorded; these are single-run timings, not a controlled latency benchmark. Checkpoints total roughly 1.15 GB and remain in `D:/ChargeWise_Cache/huggingface`, outside the repository. The app does not install or load these models.

To reproduce, use an optional Python environment with PyTorch and `chronos-forecasting==2.3.2`, `timesfm==2.0.2`, `transformers==4.57.6`, plus their dependencies. Do not install them into the lean application environment. Then:

```powershell
python scripts/foundation_forecast.py --cache D:/ChargeWise_Cache/huggingface
uv run python scripts/forecast_benchmark.py --predictions .cache/foundation-predictions.json
```

The runner pins public model revisions, disables implicit tokens and keeps negative-price forecasts. No Nebius API key is read or used, and this does not satisfy the hackathon's NVIDIA-on-Nebius runtime requirement. Primary model/library links and limitations are in the protocol.
