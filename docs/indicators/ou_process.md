# Ornstein-Uhlenbeck Process Indicators

Purpose:

- estimate whether a series has measurable mean-reversion speed and where price
  sits relative to the estimated equilibrium

## Features

| Feature | Meaning | Required Inputs |
|---|---|---|
| `OU_Theta` | Mean-reversion speed estimate. | source series, fit window |
| `OU_Mu` | Estimated equilibrium level. | source series, fit window |
| `OU_Sigma` | Residual volatility estimate. | source series, fit window |
| `OU_HalfLife` | Expected bars to mean-revert halfway. | `OU_Theta` |
| `OU_R2` | Fit quality. | regression output |
| `OU_ZScore` | Distance from `OU_Mu` normalized by `OU_Sigma`. | source, `OU_Mu`, `OU_Sigma` |

## Implementation Approach

Shared math can live in:

```text
shared/indicators/ou.py
```

Expected functions:

```text
fit_ou_window(series_window)
rolling_ou(series, window)
ou_zscore(series, ou_mu, ou_sigma)
```

## Parameter Decisions

Each strategy must state:

- source series: close, VWAP deviation, spread, or residual
- fit window
- minimum observations
- handling for invalid theta
- max half-life allowed, if used as a rule

## Causality

Rolling O-U estimates at bar N must fit only data through N.

No full-sample equilibrium estimate for trade-driving use.

## Test Plan

- synthetic O-U-like series
- random-walk-like series
- invalid/near-zero theta behavior
- causality test by mutating future bars

