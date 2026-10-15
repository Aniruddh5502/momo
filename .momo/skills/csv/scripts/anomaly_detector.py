import pandas as pd
import argparse
import sys

def detect_anomalies(file_path, column, lower_bound=0.0, upper_bound=50.0, std_threshold=3):
    try:
        df = pd.read_csv(file_path)
        if column not in df.columns:
            print(f"Error: Column {column} not found in {file_path}")
            return

        # Drop NaNs for statistical calculation
        data = df[column].dropna()
        mean = data.mean()
        std = data.std()
        
        anomalies = []
        
        for idx, row in df.iterrows():
            val = row[column]
            if pd.isna(val):
                continue
                
            # Check Out of Bounds
            if val < lower_bound or val > upper_bound:
                anomalies.append((row['Design_ID'], val, "Out of Bound"))
            
            # Check Statistical Outlier
            elif abs(val - mean) > std_threshold * std:
                anomalies.append((row['Design_ID'], val, "Statistical Outlier"))
        
        return anomalies, mean, std

    except Exception as e:
        print(f"Error processing file: {e}")
        return None, None, None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect anomalies in a CSV column.")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument("--column", required=True, help="Column to analyze")
    parser.add_argument("--lower", type=float, default=0.0, help="Lower bound for OOB check")
    parser.add_argument("--upper", type=float, default=50.0, help="Upper bound for OOB check")
    parser.add_argument("--std", type=float, default=3.0, help="Std dev threshold for outliers")
    
    args = parser.parse_args()
    
    results, mean, std = detect_anomalies(args.file, args.column, args.lower, args.upper, args.std)
    
    if results is not None:
        print(f"Analysis for {args.column}:")
        print(f"Mean: {mean:.4f}, Std Dev: {std:.4f}")
        print("-" * 40)
        if not results:
            print("No anomalies detected.")
        else:
            print(f"Found {len(results)} anomalies:")
            for design_id, val, reason in results:
                print(f"Design_ID: {design_id} | Value: {val:.4f} | Reason: {reason}")
