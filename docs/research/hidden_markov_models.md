# Hidden Markov Models for Regime Detection

**Status:** Documented

---

## What Is It?

A Hidden Markov Model (HMM) is a statistical model where the system is assumed to be in one of several **hidden states** (regimes), with each state producing observable outputs (returns, volatility) according to some probability distribution. The "hidden" part means we can't directly observe which regime the market is in — we infer it from price behavior.

**In trading:** Use HMM to identify whether the market is currently in a **trending**, **mean-reverting**, or **volatile/choppy** regime. Only trade strategies appropriate to the current regime.

---

## The Two Most Useful Models

### 2-State Model: Trending vs. Mean-Reverting

```
State 0 (Mean-Reverting): low volatility, negative return autocorrelation
State 1 (Trending):        higher volatility, positive return autocorrelation
```

### 3-State Model: Bull Trend / Chop / Bear Trend

```
State 0 (Bull):    positive mean return, moderate volatility
State 1 (Chop):    near-zero mean return, low-moderate volatility, MR
State 2 (Bear):    negative mean return, high volatility
```

---

## Mathematical Basis

### Components

```
π   = initial state probabilities: P(s₁ = i)
A   = transition matrix: A[i,j] = P(s[t+1]=j | s[t]=i)
B   = emission probabilities: B[i](y) = P(y[t] | s[t]=i)
      (Gaussian: parameterized by mean μᵢ and variance σᵢ² per state)
```

### Viterbi Algorithm
Finds the most likely sequence of hidden states given observations.

### Forward-Backward Algorithm
Computes posterior probability P(s[t]=i | all observations) — the smoothed regime probability.

### Baum-Welch (EM Algorithm)
Learns parameters (π, A, B) from data without labeled states.

---

## Why Quants Use It

1. **Unsupervised regime detection** — no labels needed, learns from price data
2. **Probabilistic output** — gives P(regime=MR | data) not just a binary flag
3. **Persistence** — transition matrix encodes how long regimes last
4. **Proven in practice** — Ang & Timmermann (2012), JP Morgan, many quant funds
5. **Improves all strategies** — knowing the regime improves entry timing for any strategy

---

## Python Implementation

```python
import numpy as np
from hmmlearn.hmm import GaussianHMM
import warnings
warnings.filterwarnings('ignore')


def fit_hmm_regime(returns: np.ndarray, n_states: int = 2,
                    n_iter: int = 100, random_state: int = 42):
    """
    Fit a Gaussian HMM to return series to detect market regimes.

    Args:
        returns: 1D array of log returns (e.g., np.diff(np.log(prices)))
        n_states: 2 (MR/trending) or 3 (bull/chop/bear)
        n_iter: EM iterations
        random_state: for reproducibility

    Returns:
        model: fitted GaussianHMM
        states: most likely state sequence (Viterbi)
        state_probs: posterior state probabilities
    """
    X = returns.reshape(-1, 1)

    model = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=n_iter,
        random_state=random_state
    )
    model.fit(X)

    states = model.predict(X)
    state_probs = model.predict_proba(X)

    return model, states, state_probs


def identify_regime_states(model, n_states: int = 2):
    """
    After fitting, identify which state = MR and which = trending.
    Low volatility state = MR. High volatility = trending/volatile.
    """
    means = model.means_.flatten()
    stds = np.sqrt(model.covars_.flatten())

    if n_states == 2:
        # Low vol state = mean-reverting
        mr_state = np.argmin(stds)
        trend_state = 1 - mr_state
        return {"mr_state": mr_state, "trend_state": trend_state,
                "means": means, "stds": stds}

    elif n_states == 3:
        # Sort by mean return
        sorted_states = np.argsort(means)
        return {
            "bear_state": sorted_states[0],
            "chop_state": sorted_states[1],
            "bull_state": sorted_states[2],
            "means": means,
            "stds": stds
        }


def rolling_hmm_regime(prices: np.ndarray, window: int = 200, n_states: int = 2):
    """
    Rolling HMM — refit every bar to get current regime probability.
    NOTE: Computationally expensive. Use warmstart or refit every N bars.
    """
    returns = np.diff(np.log(prices))
    regime_probs = np.full((len(prices), n_states), np.nan)

    for i in range(window, len(prices)):
        window_returns = returns[i-window:i]
        try:
            model, states, probs = fit_hmm_regime(window_returns, n_states)
            state_info = identify_regime_states(model, n_states)
            regime_probs[i] = probs[-1]  # probability at current bar
        except Exception:
            pass

    return regime_probs


def get_current_regime(prices: np.ndarray, window: int = 500, n_states: int = 2):
    """
    Simple current regime check.
    Returns current state and MR probability.
    """
    returns = np.diff(np.log(prices[-window:]))
    model, states, probs = fit_hmm_regime(returns, n_states)
    state_info = identify_regime_states(model, n_states)

    current_state = states[-1]
    mr_prob = probs[-1][state_info["mr_state"]]

    return {
        "current_state": current_state,
        "mr_probability": mr_prob,
        "is_mr_regime": current_state == state_info["mr_state"],
        "state_means": state_info["means"],
        "state_stds": state_info["stds"],
    }
```

---

## Practical Usage Guide

### Initial Fitting (Offline)

```python
# Fit on full history to identify regime parameters
all_returns = np.diff(np.log(all_prices))
model, states, probs = fit_hmm_regime(all_returns, n_states=2)
state_info = identify_regime_states(model)

print(f"MR state {state_info['mr_state']}: "
      f"mean={state_info['means'][state_info['mr_state']]:.6f}, "
      f"std={state_info['stds'][state_info['mr_state']]:.6f}")
```

### Real-Time Regime Filtering (Efficient)

```python
# Refit only every 50 bars to save computation
if bar_index % 50 == 0:
    regime = get_current_regime(close[:bar_index], window=500)
    current_mr_prob = regime["mr_probability"]

# Use probability as soft filter
if current_mr_prob > 0.6:
    # High confidence MR regime — trade at full size
    position_scalar = 1.0
elif current_mr_prob > 0.4:
    # Uncertain — half size
    position_scalar = 0.5
else:
    # Trending regime — skip MR trades
    position_scalar = 0.0
```

---

## Interpreting State Parameters

After fitting a 2-state model:

| State | Mean Return | Volatility | Regime | MR Strategy |
|-------|-------------|------------|--------|-------------|
| 0 | ~0 | Low | Mean-Reverting | Trade aggressively |
| 1 | +/- large | High | Trending/Volatile | Reduce/skip |

**Rule of thumb:**
- State with lower σ → mean-reverting / ranging
- State with higher σ → trending / volatile

---

## As a Data Point (record per trade)

```python
regime = get_current_regime(close[:current_bar], window=300)
signals.append({
    ...,
    "HMM_MR_Prob": regime["mr_probability"],
    "HMM_State": regime["current_state"],
    "HMM_IsMR": regime["is_mr_regime"],
})
```

---

## Key Limitation: Label Flipping

HMM states are unordered — state 0 could be MR or trending, changes with random seed. Always use `identify_regime_states()` to determine which state is which after fitting. Never hardcode state numbers.

---

## Relationship to Other Studies

- **ADF Test** (`adf_test.md`): ADF confirms stationarity; HMM gives probability
- **Variance Ratio** (`variance_ratio.md`): MR regime has VR < 1; HMM MR state should show this
- **GARCH** (`garch_volatility.md`): GARCH captures volatility clustering; combine with HMM for vol-regime

---

## References

- Hamilton, J.D. (1989) — "A New Approach to the Economic Analysis of Nonstationary Time Series"
- Ang & Timmermann (2012) — "Regime Changes and Financial Markets"
- Nystrup, Madsen & Lindström (2017) — "Long-Run Risk, Regime Switching, and HMM"
- hmmlearn library: https://hmmlearn.readthedocs.io/
