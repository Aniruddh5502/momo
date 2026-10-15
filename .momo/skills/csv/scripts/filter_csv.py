import pandas as pd
import argparse
import sys
import os

def filter_csv(file_path, output_path=None):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        sys.exit(1)

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    # Define "Failed" as: status != 'completed' OR any of the results are NaN
    result_cols = [col for col in df.columns if 'max_' in col or 'mode_' in col]
    
    # Mask for failed rows
    failed_mask = (df['status'] != 'completed') | (df[result_cols].isnull().any(axis=1))
    failed_df = df[failed_mask]

    design_ids = failed_df['Design_ID'].tolist()
    
    print(f"Found {len(design_ids)} failed simulations.")
    print(f"Design IDs: {design_ids}")

    if output_path:
        failed_df.to_csv(output_path, index=False)
        print(f"Filtered results saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter CSV for failed simulations.")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument("--out", help="Optional path to save filtered CSV")
    args = parser.parse_args()
    
    filter_csv(args.file, args.out)
