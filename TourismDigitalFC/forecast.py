import argparse
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def load_series(csv_path: str) -> pd.Series:
    df = pd.read_csv(csv_path, parse_dates=["Date"])  # expects Date and Visitor_Count columns
    df = df.sort_values("Date")
    df = df.set_index("Date")
    y = df["Visitor_Count"].astype(float)  
    y = y.asfreq("D")
    return y


def fit_and_forecast(y: pd.Series, periods: int) -> pd.DataFrame:
    try:
        import pmdarima as pm
        model = pm.auto_arima(
            y,
            seasonal=True,
            m=7,
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            trace=False,
        )
        fc_vals = model.predict(n_periods=periods)
    except Exception:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        model = SARIMAX(y, order=(1, 1, 1), seasonal_order=(1, 1, 1, 7))
        res = model.fit(disp=False)
        fc_vals = res.forecast(steps=periods)
    last_date = y.index.max()
    future_index = pd.date_range(last_date + pd.Timedelta(days=1), periods=periods, freq="D")
    fc_df = pd.DataFrame({"Date": future_index, "Forecast_Visitor_Count": np.maximum(fc_vals, 0)})
    fc_df["Forecast_Visitor_Count"] = fc_df["Forecast_Visitor_Count"].round().astype(int)
    return fc_df


def plot_forecast(y: pd.Series, fc_df: pd.DataFrame, output_path: str) -> None:
    recent = y.tail(120)
    plt.figure(figsize=(12, 5))
    plt.plot(recent.index, recent.values, label="Observed", color="#1f77b4")
    plt.plot(fc_df["Date"], fc_df["Forecast_Visitor_Count"].values, label="Forecast", color="#d62728")
    plt.title("Sigiriya Visitor Count Forecast")
    plt.xlabel("Date")
    plt.ylabel("Visitors")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Visitor Count Forecasting")
    parser.add_argument("--csv", default="sigiriya_synthetic_visitors_2023_2025.csv")
    parser.add_argument("--periods", type=int, default=90)
    parser.add_argument("--out_csv", default="forecast_output.csv")
    parser.add_argument("--out_plot", default="forecast_plot.png")
    args = parser.parse_args()

    y = load_series(args.csv)
    fc_df = fit_and_forecast(y, args.periods)
    fc_df.to_csv(args.out_csv, index=False)
    plot_forecast(y, fc_df, args.out_plot)
    print(f"Saved: {args.out_csv}")
    print(f"Saved: {args.out_plot}")


if __name__ == "__main__":
    main()
