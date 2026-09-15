"""
Tabular Data Cleaning Benchmark Suites and Held-Out Validation Cases.
Defines ground-truth test cases and realistic dirty datasets for Domain 1.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

def get_held_out_tabular_test_cases(subtask: str) -> List[Dict[str, Any]]:
    """Returns rigorous held-out test cases for sandboxed skill validation."""
    if subtask == "missing_value_imputation":
        # Case 1: Pure numeric DataFrame with known median
        df1 = pd.DataFrame({"score": [10.0, 20.0, np.nan, 40.0, 50.0]})
        # Case 2: Mixed numeric and categorical
        df2 = pd.DataFrame({"age": [25.0, np.nan, 35.0], "dept": ["HR", "HR", None]})
        # Case 3: Edge case - all NaNs
        df3 = pd.DataFrame({"val": [np.nan, np.nan, np.nan]})

        return [
            {
                "description": "Impute numeric column with median",
                "inputs": [df1],
                "assertion_fn": lambda res: isinstance(res, pd.DataFrame) and res["score"].isnull().sum() == 0 and res["score"].iloc[2] == 30.0
            },
            {
                "description": "Impute categorical column with mode",
                "inputs": [df2],
                "assertion_fn": lambda res: isinstance(res, pd.DataFrame) and res["dept"].isnull().sum() == 0 and res["dept"].iloc[2] == "HR"
            },
            {
                "description": "Handle all-NaN edge column",
                "inputs": [df3],
                "assertion_fn": lambda res: isinstance(res, pd.DataFrame) and res["val"].isnull().sum() == 0
            }
        ]

    elif subtask == "type_coercion":
        df1 = pd.DataFrame({"price": ["$10.50", "$20.00", "$30.25"]})
        df2 = pd.DataFrame({"rate": ["12.5%", "18.0%", "5.5%"]})
        df3 = pd.DataFrame({"revenue": ["1,000", "2,500", "10,000"]})

        return [
            {
                "description": "Strip currency symbols and coerce to float",
                "inputs": [df1],
                "assertion_fn": lambda res: pd.api.types.is_numeric_dtype(res["price"]) and res["price"].sum() == 60.75
            },
            {
                "description": "Strip percentage symbols and cast to numeric",
                "inputs": [df2],
                "assertion_fn": lambda res: pd.api.types.is_numeric_dtype(res["rate"]) and res["rate"].iloc[0] == 12.5
            },
            {
                "description": "Remove commas and cast integers to numeric",
                "inputs": [df3],
                "assertion_fn": lambda res: pd.api.types.is_numeric_dtype(res["revenue"]) and res["revenue"].iloc[2] == 10000.0
            }
        ]

    elif subtask == "duplicate_removal":
        df1 = pd.DataFrame({"id": [1, 2, 2, 3], "val": ["A", "B", "B", "C"]})
        df2 = pd.DataFrame({"x": [1, 1, 1, 1]})

        return [
            {
                "description": "Remove duplicated records and reset index",
                "inputs": [df1],
                "assertion_fn": lambda res: len(res) == 3 and res.duplicated().sum() == 0
            },
            {
                "description": "Deduplicate all identical entries",
                "inputs": [df2],
                "assertion_fn": lambda res: len(res) == 1
            }
        ]

    elif subtask == "outlier_handling":
        # Q1 = 10, Q3 = 14, IQR = 4. Lower bound = 10 - 6 = 4, Upper bound = 14 + 6 = 20
        df1 = pd.DataFrame({"val": [10.0, 11.0, 12.0, 13.0, 14.0, 100.0, -50.0]})

        return [
            {
                "description": "Cap outliers using IQR fences",
                "inputs": [df1],
                "assertion_fn": lambda res: res["val"].max() <= 20.0 and res["val"].min() >= 4.0
            }
        ]

    elif subtask == "column_name_standardization":
        df1 = pd.DataFrame(columns=[" First Name ", "Last-Name", "Annual Revenue ($)"])
        df1.loc[0] = [1, 2, 3]

        return [
            {
                "description": "Standardize dirty headers to snake_case",
                "inputs": [df1],
                "assertion_fn": lambda res: list(res.columns) == ["first_name", "last_name", "annual_revenue"]
            }
        ]

    elif subtask == "date_parsing_normalization":
        df1 = pd.DataFrame({"event_date": ["2024/01/15", "2023-11-20", "2022.05.04"]})

        return [
            {
                "description": "Normalize heterogeneous dates to ISO-8601 YYYY-MM-DD",
                "inputs": [df1],
                "assertion_fn": lambda res: list(res["event_date"]) == ["2024-01-15", "2023-11-20", "2022-05-04"]
            }
        ]

    return []


def generate_sample_dirty_dataset(name: str = "customer_churn") -> pd.DataFrame:
    """Generates synthetic, realistic messy datasets for live workbench experimentation."""
    np.random.seed(42)

    if name == "healthcare":
        data = {
            " Patient ID# ": [f"P_{100+i}" for i in range(25)] + [f"P_100", f"P_101"], # duplicates
            "Patient Age": [25, 45, -5, 34, np.nan, 52, 61, 29, 300, 41, 38, np.nan, 47, 50, 62, 33, 44, 28, 59, 65, 31, 48, 53, 39, 42, 25, 45],
            "Blood-Pressure": ["120/80", "$130", "140/90", None, "125/82", "118/75", "135/88", "122/80", "$145", "128/84", "130/85", "120/80", "115/70", "142/92", "138/86", "124/82", "126/80", "132/85", "129/83", "140/90", "122/78", "136/88", "125/82", "131/85", "127/81", "120/80", "$130"],
            "Cholesterol (mg/dL)": [180.0, 210.0, np.nan, 195.0, 220.0, 185.0, 240.0, 999.0, 175.0, 205.0, 190.0, 215.0, 225.0, 230.0, 182.0, 200.0, 212.0, 188.0, 245.0, 208.0, 192.0, 218.0, 222.0, 198.0, 204.0, 180.0, 210.0],
            "Registration Date": ["2024/01/10", "2023-12-05", "2024.02.18", "15-03-2024", "2024/04/01"] * 5 + ["2024/01/10", "2023-12-05"]
        }
        return pd.DataFrame(data)

    elif name == "ecommerce":
        data = {
            "Order ID": [1000 + i for i in range(25)] + [1000, 1001],
            "Customer Name": ["Alice", "Bob", None, "Diana", "Evan", "Fiona", "George", "Hannah", "Ian", "Jane", "Kyle", None, "Mia", "Noah", "Olivia", "Paul", "Quinn", "Rose", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander", "Yara", "Alice", "Bob"],
            "Total Amount": ["$120.50", "$45.00", "$300.00", "$15.99", "$85.20", "$1,250.00", "$50.00", "$75.40", "$99.99", "$210.00", "$35.50", "$180.00", "$65.00", "$420.00", "$15.00", "$89.90", "$145.00", "$60.00", "$320.00", "$78.50", "$110.00", "$95.00", "$250.00", "$18.00", "$130.00", "$120.50", "$45.00"],
            "Discount %": ["5%", "10%", "0%", "15%", "20%", "5%", "10%", "0%", "12%", "8%", "5%", "15%", "0%", "25%", "5%", "10%", "15%", "0%", "10%", "5%", "8%", "12%", "20%", "5%", "0%", "5%", "10%"],
            "Purchase Date": ["2024-05-01", "2024/05/02", "03-05-2024", "2024.05.04", "2024-05-05"] * 5 + ["2024-05-01", "2024/05/02"]
        }
        return pd.DataFrame(data)

    # Default: Customer Churn
    data = {
        " Customer ID ": [f"C_{100+i}" for i in range(30)] + ["C_100", "C_101"], # duplicates
        "Tenure Months": [12, 24, np.nan, 5, 36, 48, 2, 60, 15, 20, 8, np.nan, 42, 55, 3, 18, 30, 22, 50, 65, 10, 28, 33, 7, 45, 14, 52, 9, 38, 25, 12, 24],
        "Monthly Charges": ["$65.50", "$89.00", "$29.99", "$105.20", "$45.00", "$120.00", "$35.50", "$75.00", "$92.40", "$58.00", "$110.50", "$40.00", "$85.00", "$99.90", "$25.00", "$70.00", "$88.50", "$62.00", "$104.00", "$115.00", "$32.00", "$78.00", "$90.00", "$48.00", "$102.00", "$55.00", "$112.00", "$38.00", "$82.00", "$68.00", "$65.50", "$89.00"],
        "Total Spend": [1200.0, 2400.0, np.nan, 600.0, 4200.0, 5800.0, 150.0, 7200.0, 1800.0, 2100.0, 950.0, 800.0, 4800.0, 6200.0, 200.0, 1900.0, 3100.0, 2300.0, 5900.0, 99999.0, 1100.0, 2900.0, 3500.0, 750.0, 5100.0, 1600.0, 6000.0, 980.0, 4100.0, 2600.0, 1200.0, 2400.0],
        "Churn Status": ["Yes", "No", "No", "Yes", None, "No", "Yes", "No", "No", "Yes", "Yes", None, "No", "No", "Yes", "No", "No", "Yes", "No", "No", "Yes", "No", "No", "Yes", "No", "Yes", "No", "Yes", "No", "No", "Yes", "No"],
        "Join Date": ["2023/01/15", "2022-06-20", "2024.03.10", "11-09-2021", "2023-10-05"] * 6 + ["2023/01/15", "2022-06-20"]
    }
    return pd.DataFrame(data)