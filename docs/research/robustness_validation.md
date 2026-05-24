# Robustness Validation & Overfitting Detection

Architecture note:

This is preserved research material, not the active workflow definition. Do not
recreate ranking agents, production-readiness scoring, or broad strategy
ranking pipelines from this note. The active validation plan lives in
`docs/overfitting_tests/` and the parent/child workflow docs; implementation
names in this background note may be superseded by those active specs.

## Summary

After backtesting produces results, those results must be validated to ensure they reflect genuine market edge rather than overfitting to historical noise. This document catalogues the standard statistical methods used by quantitative funds to separate signal from noise in backtest results.

**Two-tier ranking system:**
- **Tier 1 (Raw):** Rank by backtest performance metrics (hit rate, expectancy, Sharpe, etc.)
- **Tier 2 (Validated):** Re-rank after passing robustness tests — only strategies surviving validation are considered "production-ready"

## The 8 Robustness Tests

### Test 1: Monte Carlo Permutation Test

**What it tests:** Is the strategy's performance statistically distinguishable from random?

**Method:**
1. Take the strategy's actual trade sequence (wins/losses with R-multiples)
2. Randomly shuffle the trade order N times (typically N=10,000)
3. For each shuffle, recompute the equity curve and key metrics
4. Compare the actual strategy's metric to the distribution of shuffled metrics
5. Compute p-value: what fraction of random shuffles beat the actual result?

**Python Implementation:**
```python
import numpy as np

def monte_carlo_permutation(trade_returns, n_simulations=10000, metric_fn=None):
    """
    Monte Carlo permutation test for strategy validation.

    Args:
        trade_returns: array of R-multiples per trade
        n_simulations: number of random shuffles
        metric_fn: function(returns) -> scalar metric (default: cumulative return)

    Returns:
        dict with actual_metric, p_value, distribution
    """
    if metric_fn is None:
        metric_fn = lambda r: np.sum(r)

    actual_metric = metric_fn(trade_returns)

    sim_metrics = np.zeros(n_simulations)
    for i in range(n_simulations):
        shuffled = np.random.permutation(trade_returns)
        sim_metrics[i] = metric_fn(shuffled)

    # p-value: fraction of simulations that beat actual
    p_value = np.mean(sim_metrics >= actual_metric)

    return {
        "actual_metric": actual_metric,
        "p_value": p_value,
        "mean_random": np.mean(sim_metrics),
        "std_random": np.std(sim_metrics),
        "percentile_99": np.percentile(sim_metrics, 99),
        "distribution": sim_metrics
    }
```

**Thresholds:**
| p-value | Interpretation |
|---------|---------------|
| < 0.01  | Strong evidence of real edge |
| 0.01-0.05 | Moderate evidence |
| 0.05-0.10 | Weak evidence |
| > 0.10 | Cannot distinguish from random — likely overfitted |

---

### Test 2: Monte Carlo Equity Curve Simulation

**What it tests:** What is the range of possible outcomes given the strategy's win rate and payoff distribution?

**Method:**
1. Estimate the strategy's win rate and return distribution from backtest
2. Generate N synthetic equity curves by sampling from this distribution
3. Compute confidence intervals for drawdown, final equity, and Sharpe
4. Check if the actual backtest falls within a reasonable band

**Python Implementation:**
```python
def monte_carlo_equity_curves(trade_returns, n_simulations=5000, n_trades=None):
    """
    Generate synthetic equity curves by resampling trades with replacement.

    Args:
        trade_returns: array of R-multiples per trade
        n_simulations: number of synthetic curves
        n_trades: trades per curve (default: same as actual)

    Returns:
        dict with drawdown distribution, final equity distribution
    """
    if n_trades is None:
        n_trades = len(trade_returns)

    final_equities = np.zeros(n_simulations)
    max_drawdowns = np.zeros(n_simulations)

    for i in range(n_simulations):
        # Resample trades with replacement (bootstrap)
        sampled = np.random.choice(trade_returns, size=n_trades, replace=True)
        equity_curve = np.cumsum(sampled)

        final_equities[i] = equity_curve[-1]

        # Max drawdown in R-multiples
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = running_max - equity_curve
        max_drawdowns[i] = np.max(drawdowns)

    return {
        "median_final_equity": np.median(final_equities),
        "ci_5_final": np.percentile(final_equities, 5),
        "ci_95_final": np.percentile(final_equities, 95),
        "prob_profitable": np.mean(final_equities > 0),
        "median_max_dd": np.median(max_drawdowns),
        "ci_95_max_dd": np.percentile(max_drawdowns, 95),
        "worst_case_dd": np.percentile(max_drawdowns, 99)
    }
```

---

### Test 3: Walk-Forward Analysis (WFA)

**What it tests:** Does the strategy work on data it wasn't trained on?

**Method:**
1. Divide the data into sequential windows (e.g., 6-month in-sample + 2-month out-of-sample)
2. Optimize/fit on in-sample, test on out-of-sample
3. Roll forward and repeat across the full history
4. The "walk-forward efficiency" = OOS performance / IS performance
5. WFE > 0.5 generally acceptable; < 0.3 suggests overfitting

**Python Implementation:**
```python
def walk_forward_analysis(trades_df, n_splits=8, is_ratio=0.75):
    """
    Walk-forward analysis: split trades chronologically, test IS vs OOS.

    Args:
        trades_df: DataFrame with DateTime, Hit1R, R_multiple columns
        n_splits: number of walk-forward windows
        is_ratio: fraction of each window used for in-sample

    Returns:
        dict with per-window IS/OOS metrics and walk-forward efficiency
    """
    trades_sorted = trades_df.sort_values("DateTime")
    n = len(trades_sorted)
    window_size = n // n_splits

    results = []
    for i in range(n_splits):
        start = i * window_size
        end = min(start + window_size, n)
        window = trades_sorted.iloc[start:end]

        split_point = int(len(window) * is_ratio)
        is_trades = window.iloc[:split_point]
        oos_trades = window.iloc[split_point:]

        if len(oos_trades) < 10:
            continue

        is_hit_rate = is_trades["Hit1R"].mean()
        oos_hit_rate = oos_trades["Hit1R"].mean()

        results.append({
            "window": i + 1,
            "is_trades": len(is_trades),
            "oos_trades": len(oos_trades),
            "is_hit_rate": is_hit_rate,
            "oos_hit_rate": oos_hit_rate,
            "wf_efficiency": oos_hit_rate / is_hit_rate if is_hit_rate > 0 else 0
        })

    avg_wfe = np.mean([r["wf_efficiency"] for r in results])

    return {
        "windows": results,
        "avg_walk_forward_efficiency": avg_wfe,
        "verdict": "PASS" if avg_wfe > 0.5 else "WARN" if avg_wfe > 0.3 else "FAIL"
    }
```

**Thresholds:**
| WF Efficiency | Interpretation |
|---------------|---------------|
| > 0.7 | Excellent — strategy generalizes well |
| 0.5-0.7 | Good — likely real edge |
| 0.3-0.5 | Marginal — may be partially overfitted |
| < 0.3 | Poor — likely overfitted |

---

### Test 4: Deflated Sharpe Ratio (DSR)

**What it tests:** Is the Sharpe ratio statistically significant after correcting for multiple testing, non-normality, and sample length?

**Reference:** Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio"

**The Problem:** When you test N strategies, the best one's Sharpe is biased upward. DSR corrects for:
- Number of strategies tested (multiple hypothesis correction)
- Non-normal returns (skewness and kurtosis)
- Sample length (short backtests inflate Sharpe)

**Formula:**
```
DSR = PSR(SR_benchmark)

where SR_benchmark = SR* × √(V[{SRk}])

SR* = expected max Sharpe from N trials ≈ (1 - γ) × Φ^{-1}(1 - 1/N) + γ × Φ^{-1}(1 - 1/(N×e))
     where γ ≈ 0.5772 (Euler-Mascheroni constant)

PSR = Prob[SR > SR_benchmark]
    = Φ( √(T-1) × (SR_hat - SR_benchmark) / √(1 - γ3×SR_hat + (γ4-1)/4 × SR_hat²) )

where:
    T = number of observations
    SR_hat = observed Sharpe ratio
    γ3 = skewness of returns
    γ4 = kurtosis of returns
```

**Python Implementation:**
```python
from scipy import stats

def deflated_sharpe_ratio(returns, n_strategies_tested, risk_free=0):
    """
    Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

    Corrects for multiple testing, non-normality, and sample length.

    Args:
        returns: array of strategy returns (per-trade R-multiples)
        n_strategies_tested: total number of strategies/configs tested
        risk_free: risk-free rate (usually 0 for intraday)

    Returns:
        dict with observed SR, deflated SR, p-value, verdict
    """
    T = len(returns)
    sr_hat = (np.mean(returns) - risk_free) / np.std(returns, ddof=1)
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns, fisher=True))  # excess kurtosis

    # Expected max Sharpe from N independent trials
    euler_gamma = 0.5772156649
    N = n_strategies_tested
    if N > 1:
        sr_benchmark = (
            (1 - euler_gamma) * stats.norm.ppf(1 - 1/N) +
            euler_gamma * stats.norm.ppf(1 - 1/(N * np.e))
        ) * (1 / np.sqrt(T))
    else:
        sr_benchmark = 0

    # Probabilistic Sharpe Ratio
    numerator = (sr_hat - sr_benchmark) * np.sqrt(T - 1)
    denominator = np.sqrt(1 - skew * sr_hat + ((kurt - 1) / 4) * sr_hat**2)

    if denominator <= 0:
        dsr = 0.0
    else:
        dsr = float(stats.norm.cdf(numerator / denominator))

    return {
        "observed_sharpe": sr_hat,
        "benchmark_sharpe": sr_benchmark,
        "deflated_sharpe_pvalue": dsr,
        "skewness": skew,
        "kurtosis": kurt,
        "n_observations": T,
        "n_strategies": N,
        "verdict": "PASS" if dsr > 0.95 else "WARN" if dsr > 0.85 else "FAIL"
    }
```

**Thresholds:**
| DSR p-value | Interpretation |
|-------------|---------------|
| > 0.95 | Sharpe is real even after correcting for all biases |
| 0.85-0.95 | Marginal — be cautious |
| < 0.85 | Sharpe is likely inflated by data mining |

---

### Test 5: Combinatorially Symmetric Cross-Validation (CSCV) & Probability of Backtest Overfitting (PBO)

**What it tests:** What is the probability that the best strategy in-sample is NOT the best out-of-sample?

**Reference:** Bailey, Borwein, Lopez de Prado, Zhu (2015)

**Method:**
1. Partition the backtest data into S equal sub-samples (typically S=16)
2. Form all C(S, S/2) combinations of S/2 sub-samples for training
3. The remaining S/2 sub-samples form the test set
4. For each combination, find the best strategy IS, then measure its rank OOS
5. PBO = fraction of combinations where the IS-best strategy underperforms the median OOS

**Python Implementation:**
```python
from itertools import combinations

def cscv_pbo(returns_matrix, n_partitions=16):
    """
    Combinatorially Symmetric Cross-Validation for PBO.

    Args:
        returns_matrix: (T, N) matrix — T time periods, N strategies
        n_partitions: number of sub-samples (must be even)

    Returns:
        dict with PBO, logit distribution, verdict
    """
    T, N = returns_matrix.shape
    partition_size = T // n_partitions

    # Create partitions
    partitions = []
    for i in range(n_partitions):
        start = i * partition_size
        end = start + partition_size
        partitions.append(returns_matrix[start:end])

    half = n_partitions // 2
    combos = list(combinations(range(n_partitions), half))

    # Limit to manageable number of combinations
    if len(combos) > 1000:
        indices = np.random.choice(len(combos), 1000, replace=False)
        combos = [combos[i] for i in indices]

    n_overfit = 0
    logits = []

    for combo in combos:
        test_indices = [i for i in range(n_partitions) if i not in combo]

        # In-sample: concatenate training partitions
        is_data = np.vstack([partitions[i] for i in combo])
        oos_data = np.vstack([partitions[i] for i in test_indices])

        # Performance of each strategy IS and OOS
        is_perf = np.mean(is_data, axis=0)  # mean return per strategy
        oos_perf = np.mean(oos_data, axis=0)

        # Best strategy in-sample
        best_is = np.argmax(is_perf)

        # Rank of that strategy out-of-sample
        oos_rank = np.sum(oos_perf >= oos_perf[best_is]) / N

        # Overfit if IS-best is below median OOS
        if oos_rank > 0.5:
            n_overfit += 1

        # Logit of relative rank
        w = oos_rank
        if 0 < w < 1:
            logits.append(np.log(w / (1 - w)))

    pbo = n_overfit / len(combos)

    return {
        "pbo": pbo,
        "n_combinations": len(combos),
        "mean_logit": np.mean(logits) if logits else None,
        "verdict": "PASS" if pbo < 0.30 else "WARN" if pbo < 0.50 else "FAIL"
    }
```

**Thresholds:**
| PBO | Interpretation |
|-----|---------------|
| < 0.15 | Low overfitting risk — strategy generalizes |
| 0.15-0.30 | Moderate risk |
| 0.30-0.50 | High risk — likely overfitted |
| > 0.50 | Very high — IS-best is worse than median OOS |

**Note:** CSCV requires testing multiple strategies/parameter configurations. It's most useful after a parameter sweep, not for a single config.

---

### Test 6: Minimum Backtest Length (MinBTL)

**What it tests:** Is your backtest long enough to trust the Sharpe ratio?

**Reference:** Bailey & Lopez de Prado (2012)

**Formula:**
```
MinBTL = 1 + (1 - γ3 × SR + (γ4 - 1)/4 × SR²) × (z_α / SR)²

where:
    γ3 = skewness
    γ4 = kurtosis
    SR = annualized Sharpe ratio
    z_α = critical value (1.96 for 95% confidence)
    Result is in years (or whatever the return frequency unit is)
```

**Python Implementation:**
```python
def minimum_backtest_length(returns, confidence=0.95):
    """
    Minimum Backtest Length (Bailey & Lopez de Prado, 2012).

    Returns the minimum number of observations needed for the
    Sharpe ratio to be statistically significant.

    Args:
        returns: array of trade returns
        confidence: confidence level (default 0.95)

    Returns:
        dict with min_length, actual_length, verdict
    """
    sr = np.mean(returns) / np.std(returns, ddof=1)
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns, fisher=True))
    z_alpha = stats.norm.ppf(1 - (1 - confidence) / 2)

    if abs(sr) < 1e-10:
        min_length = float('inf')
    else:
        min_length = (
            1 + (1 - skew * sr + ((kurt - 1) / 4) * sr**2) *
            (z_alpha / sr)**2
        )

    actual_length = len(returns)

    return {
        "min_trades_needed": int(np.ceil(max(min_length, 0))),
        "actual_trades": actual_length,
        "sufficient": actual_length >= min_length,
        "verdict": "PASS" if actual_length >= min_length else "FAIL"
    }
```

---

### Test 7: White's Reality Check / Hansen's Superior Predictive Ability (SPA)

**What it tests:** Among all strategies tested, does the best one genuinely outperform a benchmark (typically buy-and-hold or zero return), correcting for the fact that we tested many?

**Reference:** White (2000), Hansen (2005)

**Method:**
1. Compute performance advantage of each strategy over the benchmark
2. Bootstrap the time series of advantages (block bootstrap to preserve autocorrelation)
3. Under H0: no strategy is genuinely better than benchmark
4. p-value = fraction of bootstraps where the max advantage exceeds the actual max

**Python Implementation:**
```python
def whites_reality_check(strategy_returns_matrix, benchmark_returns=None,
                          n_bootstrap=5000, block_size=10):
    """
    White's Reality Check / Hansen's SPA test.

    Tests whether the best strategy genuinely outperforms the benchmark
    after correcting for multiple testing.

    Args:
        strategy_returns_matrix: (T, N) matrix of aligned returns
        benchmark_returns: (T,) benchmark returns (default: zeros)
        n_bootstrap: number of bootstrap samples
        block_size: block size for circular block bootstrap

    Returns:
        dict with p_value, best_strategy_index, verdict
    """
    T, N = strategy_returns_matrix.shape
    if benchmark_returns is None:
        benchmark_returns = np.zeros(T)

    # Excess returns over benchmark
    excess = strategy_returns_matrix - benchmark_returns.reshape(-1, 1)

    # Actual best performance
    mean_excess = np.mean(excess, axis=0)
    actual_max = np.max(mean_excess)
    best_idx = np.argmax(mean_excess)

    # Block bootstrap
    boot_maxes = np.zeros(n_bootstrap)
    n_blocks = T // block_size + 1

    for b in range(n_bootstrap):
        # Circular block bootstrap
        block_starts = np.random.randint(0, T, size=n_blocks)
        indices = []
        for start in block_starts:
            indices.extend(range(start, start + block_size))
        indices = [i % T for i in indices[:T]]

        boot_excess = excess[indices]
        boot_max = np.max(np.mean(boot_excess, axis=0))
        boot_maxes[b] = boot_max

    # Center the bootstrap distribution
    boot_maxes_centered = boot_maxes - actual_max
    p_value = np.mean(boot_maxes_centered >= 0)

    return {
        "p_value": p_value,
        "best_strategy_index": int(best_idx),
        "best_mean_excess": float(actual_max),
        "verdict": "PASS" if p_value < 0.05 else "WARN" if p_value < 0.10 else "FAIL"
    }
```

---

### Test 8: Parameter Stability Analysis

**What it tests:** Does performance degrade smoothly or catastrophically when parameters change slightly?

**Method:**
1. Run a parameter sweep around the chosen parameters (e.g., +-20%)
2. Compute performance for each parameter point
3. A robust strategy shows smooth degradation (a "plateau")
4. An overfitted strategy shows a narrow "spike" — performance collapses with tiny changes

**Python Implementation:**
```python
def parameter_stability(sweep_results_df, metric_col="hit_rate_1r"):
    """
    Analyze parameter stability from sweep results.

    A robust strategy shows a plateau (smooth degradation near optimum).
    An overfitted strategy shows a spike (performance collapses with small changes).

    Args:
        sweep_results_df: DataFrame from parameter sweep with columns for
                          each parameter and performance metrics
        metric_col: column to analyze

    Returns:
        dict with stability score, verdict
    """
    metrics = sweep_results_df[metric_col].values

    if len(metrics) < 3:
        return {"stability_score": None, "verdict": "INSUFFICIENT_DATA"}

    best_idx = np.argmax(metrics)
    best_val = metrics[best_idx]

    if best_val == 0:
        return {"stability_score": 0, "verdict": "FAIL"}

    # What fraction of neighboring configs achieve >= 80% of best?
    threshold = 0.8 * best_val
    n_above_threshold = np.sum(metrics >= threshold)
    stability_ratio = n_above_threshold / len(metrics)

    # Coefficient of variation (lower = more stable)
    cv = np.std(metrics) / np.mean(metrics) if np.mean(metrics) > 0 else float('inf')

    # Stability score: 0-100
    stability_score = min(100, stability_ratio * 100)

    return {
        "stability_score": stability_score,
        "pct_configs_above_80pct": stability_ratio,
        "coefficient_of_variation": cv,
        "best_metric": best_val,
        "median_metric": np.median(metrics),
        "worst_metric": np.min(metrics),
        "verdict": "PASS" if stability_ratio > 0.3 else "WARN" if stability_ratio > 0.15 else "FAIL"
    }
```

---

## Composite Robustness Score

After running all applicable tests, compute a composite score:

```python
def composite_robustness_score(test_results):
    """
    Combine individual test results into a single robustness score.

    Each test contributes a score from 0 to 1:
    - PASS = 1.0, WARN = 0.5, FAIL = 0.0

    Weighted average across tests.
    """
    weights = {
        "monte_carlo_permutation": 3,   # Most important: is it real?
        "monte_carlo_equity":      1,   # Informational
        "walk_forward":            3,   # Key: does it generalize?
        "deflated_sharpe":         2,   # Corrects for data mining
        "cscv_pbo":                2,   # Only if sweep was done
        "min_backtest_length":     2,   # Is sample sufficient?
        "whites_reality_check":    2,   # Multiple testing correction
        "parameter_stability":     2,   # Only if sweep was done
    }

    score_map = {"PASS": 1.0, "WARN": 0.5, "FAIL": 0.0}

    total_weight = 0
    weighted_sum = 0

    for test_name, weight in weights.items():
        if test_name in test_results and test_results[test_name].get("verdict"):
            verdict = test_results[test_name]["verdict"]
            if verdict in score_map:
                weighted_sum += score_map[verdict] * weight
                total_weight += weight

    if total_weight == 0:
        return {"composite_score": None, "verdict": "NO_TESTS"}

    score = weighted_sum / total_weight

    return {
        "composite_score": round(score * 100, 1),
        "tests_run": sum(1 for t in weights if t in test_results),
        "tests_passed": sum(1 for t in weights if t in test_results
                          and test_results[t].get("verdict") == "PASS"),
        "verdict": ("PRODUCTION_READY" if score >= 0.8 else
                    "PROMISING" if score >= 0.6 else
                    "QUESTIONABLE" if score >= 0.4 else
                    "LIKELY_OVERFITTED")
    }
```

## Validation Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  TIER 1: Raw Backtest Results                           │
│  Rank by: hit rate, expectancy, Sharpe, consistency     │
│  (strategy-ranker agent handles this)                   │
└────────────────────────┬────────────────────────────────┘
                         │ Top strategies
                         ▼
┌─────────────────────────────────────────────────────────┐
│  TIER 2: Robustness Validation                          │
│                                                          │
│  Required tests (always run):                            │
│  ✓ Monte Carlo Permutation (p < 0.05)                   │
│  ✓ Walk-Forward Analysis (WFE > 0.5)                    │
│  ✓ Minimum Backtest Length (sufficient sample)           │
│  ✓ Deflated Sharpe Ratio (DSR > 0.95)                  │
│                                                          │
│  Conditional tests (run after parameter sweep):          │
│  ✓ CSCV / PBO (PBO < 0.30)                             │
│  ✓ Parameter Stability (stability > 30%)                │
│  ✓ White's Reality Check (p < 0.05)                     │
│                                                          │
│  Optional:                                               │
│  ✓ Monte Carlo Equity Curves (risk assessment)          │
└────────────────────────┬────────────────────────────────┘
                         │ Survivors
                         ▼
┌─────────────────────────────────────────────────────────┐
│  VALIDATED RANKING                                      │
│  Only strategies with composite_score >= 60             │
│  Ranked by: composite_robustness × raw_performance      │
│  Output: data/rankings/validated_rankings.json           │
└─────────────────────────────────────────────────────────┘
```

## Layer Role

This is NOT a trading dimension — it's a **post-processing validation layer** that sits after backtesting and before production deployment.

## Column Names

No new bootstrap columns. This operates on trade-level results from `data/results/`.

## Output Files

| File | Purpose |
|------|---------|
| `data/rankings/strategy_rankings.json` | Tier 1: raw performance ranking |
| `data/rankings/validated_rankings.json` | Tier 2: robustness-validated ranking |
| `data/rankings/robustness_reports/` | Per-strategy validation reports |
| `data/rankings/configs/` | Reproducible configs for validated strategies |

## References

- Bailey, D.H. & Lopez de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality." Journal of Portfolio Management.
- Bailey, D.H., Borwein, J., Lopez de Prado, M., Zhu, Q.J. (2015). "The Probability of Backtest Overfitting." Journal of Computational Finance.
- White, H. (2000). "A Reality Check for Data Snooping." Econometrica.
- Hansen, P.R. (2005). "A Test for Superior Predictive Ability." Journal of Business & Economic Statistics.
- Lopez de Prado, M. (2018). "Advances in Financial Machine Learning." Wiley.
- Bailey, D.H. & Lopez de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier." Journal of Risk.
