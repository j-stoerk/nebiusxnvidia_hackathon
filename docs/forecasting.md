# Forecasting choice and data beyond the demo

Research checked 2026-10-24. The older TimesFM idea was a valid forecasting role. Google's model can be replaced independently of the optimizer and agent.

## Candidate: NVIDIA Kumo-Forecast

NVIDIA publishes **Kumo-Forecast**, a MOMENT-based forecasting model with historical-pattern retrieval, under Apache-2.0. It uses PyTorch and targets numeric time series. Source: [NVIDIA model card](https://huggingface.co/nvidia/Kumo-Forecast).

The current Structured Data Models adapter describes multivariate forecasting with historical covariates, 512 history steps, and a native horizon up to 72 steps. At 15-minute resolution that is 5 days 8 hours of history and an 18-hour forecast. Source: [NVIDIA adapter contract](https://nvidia.github.io/structured-data-models/api/generated/sdm.models.KumoForecast). Pin the SDK/checkpoint and test actual shapes; the broader model card lists additional sequence lengths and autoregressive extension, so these interfaces should not be treated as identical.

Recommended architecture to evaluate:

1. Historical station load → Kumo-Forecast → expected aggregate load/uncertainty.
2. Committed vehicle requirements and station limits → OR-Tools schedule.
3. Nemotron on Token Factory → approved tools and explanations.

Forecasting can help anticipate unannounced demand or background load. It must not override known vehicle energy/deadline requirements or turn a predicted value into a hard physical limit. OR-Tools remains responsible for the schedule and the validator for enforcement.

Nebius Serverless supports containerized jobs/endpoints. A self-hosted Kumo workload there is a plausible deployment route, **not a tested integration**. No managed Kumo Token Factory endpoint was verified from the public catalog. Retain Nemotron through Token Factory for the chosen Apps and Agents track. Source: [Nebius Serverless](https://docs.nebius.com/serverless), [Token Factory catalog](https://tokenfactory.nebius.com/models).

Alternative: NVIDIA's TFT implementation supports multi-horizon forecasts but entails a task-specific training workflow rather than being a simple pretrained TimesFM replacement. Its architecture originated at Google/Oxford; do not assume every NVIDIA implementation/checkpoint automatically satisfies the contest model condition. Source: [NVIDIA TFT](https://catalog.ngc.nvidia.com/orgs/nvidia/-/resources/tft_for_pytorch/-).

No weights, GPU environment, paid resources, training job, or inference service have been created. First prove the data adapter and compare pretrained forecasts against a seasonal-naive baseline. The choice is a researched candidate, not an implemented component.

## Enough data in GitHub for a demo

`data/reference/nlr_ev_load_15min.csv` has 672 chronological points from a simulated two-port 150 kW station. It can demonstrate a 512-step context plus 72-step held-out forecast without saving a large corpus. One week of one simulated profile is too narrow to establish general forecasting quality. Keep its 2020 simulated timestamps and unspecified timezone; do not align it silently with 2019 German prices/weather or claim it represents the AC demo hardware.

Measure held-out MAE/RMSE and peak-load error against previous-day same-slot/persistence forecasts. Record forecast origin, horizon, source version, units, elapsed time, and any clipping. Split by time, fit scaling on history only, and avoid overlapping train/test targets. Never provide actual future demand as a historical covariate. Report synthetic and real-source evaluation separately.

## Larger data only when a training experiment needs it

The GitHub repository holds only the demo inputs, scripts, manifests, experiment configurations, and small evaluation summaries. Put authorized larger corpora in cloud object storage (for example Nebius S3-compatible storage), and record immutable object URI/version, SHA-256, provider/license, station coverage, cadence, time range, schema, split boundaries, and transformation code in Git. Keep private data private and make the submitted demo reproducible from its small fixtures.

Forecast adaptation would need a longer chronological history across multiple weeks, seasons and station profiles, with separate validation/test periods. The original NLR archive is roughly 34 MB compressed, so it is a reasonable cloud-side starting point, but remains simulated aggregate DC load. Real-world EV forecasting would benefit from authorized ACN histories and appropriate treatment of controlled charging, missingness and site differences. Decide the forecast target and adaptation method before acquiring a large corpus.

Nemotron LoRA addresses a different problem: operator intent, typed tool arguments, grounded explanations, and exception handling. Potential examples are questions plus state snapshots, valid tool calls/results, and verified responses generated from the actual optimizer. Split by scenario/site and keep evaluation examples held out. Raw power CSVs alone are not instruction-tuning data. Do not assume LoRA is the appropriate adaptation mechanism for Kumo; verify the selected implementation's supported training path.

Training is optional. Compare any adapted model against its pretrained version and a simple baseline before making improvement claims. No fine-tuning corpus has been downloaded or training cost incurred.
