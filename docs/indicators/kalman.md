# Kalman Indicators

Purpose:

- estimate an adaptive mean and distance from that adaptive mean

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `Kalman_Mean` | Adaptive estimated mean/state. | price/deviation series, noise params |
| `Kalman_Var` | Estimated state variance. | model state |
| `Kalman_Gain` | Update sensitivity. | model state |
| `Kalman_ZScore` | Distance from Kalman mean normalized by variance. | source, mean, variance |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/kalman.py
```

Expected functions:

```text
kalman_filter_1d(series, process_noise, observation_noise, initial_state)
kalman_zscore(series, mean, variance)
```

## Parameter Decisions

Each strategy must state:

- input series
- process noise
- observation noise
- initial state method
- burn-in behavior
- whether Kalman gain is recorded or used

No hidden default noise ratios.

## Causality

Kalman updates are naturally causal if implemented sequentially.

No smoothing pass may be used for trade-driving values. A smoother uses future
observations and is not allowed for live-style signals.

## Test Plan

- constant series
- step-change series
- known sequential update example
- causality test by mutating future bars

