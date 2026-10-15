import pandas as pd
import argparse
import sys
import os

def analyze_csv(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        sys.exit(1)

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    # Basic Info
    total_rows = len(df)
    total_cols = len(df.columns)
    empty_rows = df.isnull().all(axis=1).sum()

    print(f"\n--- CSV Profile: {os.path.basename(file_path)} ---")
    print(f"Total Rows: {total_rows}")
    print(f"Total Columns: {total_cols}")
    print(f"Empty Rows: {empty_rows}")
    print("-" * 30)

    # Column Details
    print(f"{'Col #':<7} {'Header':<20} {'Type':<10} {'Nulls':<8} {'Min':<12} {'Max':<12}")
    print("-" * 69)

    for i, col in enumerate(df.columns):
        dtype = str(df[col].dtype)
        nulls = df[col].isnull().sum()
        
        # Range for numerical columns
        if pd.api.types.is_numeric_dtype(df[col]):
            c_min = df[col].min()
            c_max = df[col].max()
        else:
            c_min = "N/A"
            c_max = "N/A"

        print(f"{i:<7} {col:<20} {dtype:<10} {nulls:<8} {c_min:<12} {c_max:<12}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile a CSV file for structural and data range analysis.")
    parser.add_argument("--file", required=True, help="Path to the CSV file to analyze")
    args = parser.parse_args()
    
    analyze_csv(args.file)
