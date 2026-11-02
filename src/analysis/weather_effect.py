import pandas as pd
from scipy import stats

# A day counts as rainy when its rain plus the two previous days' is in the top 10% of the period
RAINY_QUANTILE = 0.9


# Query result in long format (day, rain_mm, group_name, tickets) -> one row per day, one
# column per group
def pivot_daily(long: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    daily = long.pivot_table(index=["day", "rain_mm"], columns="group_name", values="tickets")
    daily = daily.reset_index()[["day", "rain_mm", *groups]]
    daily["day"] = pd.to_datetime(daily["day"])
    return daily.sort_values("day", ignore_index=True)


# Compares rainy days with the average of the same weekday in the same month, which removes
# seasonality and the weekend dip; Mann-Whitney tests whether rainy days are higher
def rainy_day_effect(daily: pd.DataFrame, groups: list[str]) -> tuple[pd.DataFrame, float, int]:
    rain_3d = daily["rain_mm"].rolling(3, min_periods=1).sum()
    threshold = rain_3d.quantile(RAINY_QUANTILE)
    rainy = rain_3d >= threshold
    same_month_weekday = [daily["day"].dt.to_period("M"), daily["day"].dt.day_of_week]

    rows = []
    for group in groups:
        # 1.0 is a normal day for that month and weekday; 1.3 is 30% above it
        ratio = daily[group] / daily.groupby(same_month_weekday)[group].transform("mean")
        rows.append(
            {
                "group": group,
                "rainy_days_vs_normal_pct": 100 * (ratio[rainy].mean() - 1),
                "other_days_vs_normal_pct": 100 * (ratio[~rainy].mean() - 1),
                "p_value": stats.mannwhitneyu(
                    ratio[rainy], ratio[~rainy], alternative="greater"
                ).pvalue,
            }
        )
    return pd.DataFrame(rows).set_index("group"), threshold, int(rainy.sum())
