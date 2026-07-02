import ast

import pandas as pd

# Load your full CSV file
df = pd.read_csv('msgdp_benchmark_results.csv')

# Clean and standardize the columns
df['reason_clean'] = df['reason'].fillna('').astype(str).str.upper()
df['feasible'] = df['feasible'].astype(bool)

# 1. No T1 errors or higher
# (Does NOT contain T1, T2, or T3; can still include general unfeasible rows)
no_t1_or_higher = df[~df['reason_clean'].str.contains('T1', regex=True) & df['feasible']]

# 2. No T2 errors or higher
# (Does NOT contain T2 or T3; can contain T1 errors or general unfeasible rows)
no_t2_or_higher = df[~df['reason_clean'].str.contains('T1|T2', regex=True) & df['feasible']]

# 3. No errors at all
# (Feasible is True and the reason column is completely empty)
no_errors_at_all = df[~df['reason_clean'].str.contains('T1|T2|T3', regex=True) & df['feasible']]

# Print the final counts
print(f"No T1 errors or higher: {len(no_t1_or_higher) / len(df) * 100}%")
print(f"No T2 errors or higher: {len(no_t2_or_higher) / len(df) * 100}%")
print(f"No errors at all: {len(no_errors_at_all) / len(df) * 100}%")

# --- 1. Percentage Calculations ---
no_t1_or_higher = df[~df['reason_clean'].str.contains('T1', regex=True) & df['feasible']]
no_t2_or_higher = df[~df['reason_clean'].str.contains('T1|T2', regex=True) & df['feasible']]
no_errors_at_all = df[~df['reason_clean'].str.contains('T1|T2|T3', regex=True) & df['feasible']]

print("--- Percentages ---")
print(f"No T1 errors or higher: {len(no_t1_or_higher) / len(df) * 100:.2f}%")
print(f"No T2 errors or higher: {len(no_t2_or_higher) / len(df) * 100:.2f}%")
print(f"No errors at all: {len(no_errors_at_all) / len(df) * 100:.2f}%")
print()

# --- 2. Min / Max Summary Stats ---
print("--- Summary Statistics ---")
print(f"Time (seconds) -> Min: {df['time_seconds'].min()}, Max: {df['time_seconds'].max()}")
print(f"Estimated Cost -> Min: {df['estimated_cost'].min()}, Max: {df['estimated_cost'].max()}")