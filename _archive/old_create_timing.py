import csv
import os
import sys
import pandas as pd

def process_trial_data(file_path, output_dir):
    """
    Process trial data from either CSV or XLSX file and generate three text files:
    firstnp.txt, lastnp.txt, and probe.txt
    
    Args:
        file_path (str): Path to the input file (CSV or XLSX)
        output_dir (str, optional): Directory to save the output files. If None, uses current directory.
    """
    
    # Read CSV file
    data = []
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'env': row['env'],
                'trial': row['trial'],
                'start': float(row['start']),
                'end': float(row['end']),
                'duration': float(row['duration'])
            })

    # Initialize lists to store the results
    first_np_before_p = []
    last_np_before_p = []
    p_trials = []

    # Process the data
    current_env = None
    np_trials_in_env = []

    for row in data:
        # If we've moved to a new environment, reset the NP trials list
        if row['env'] != current_env:
            current_env = row['env']
            np_trials_in_env = []
        
        # If this is an NP trial, add it to the list
        if str(row['trial']).startswith('np'):
            np_trials_in_env.append(row)
        
        # If this is a P trial, record it and the first/last NP trials before it
        elif row['trial'] == 'p':
            p_trials.append(row)
            
            if np_trials_in_env:
                first_np_before_p.append(np_trials_in_env[0])
                last_np_before_p.append(np_trials_in_env[-1])
            
            # Reset NP trials list after finding a P trial
            np_trials_in_env = []

    # Helper function to format a row for writing to a file
    def format_row(row):
        #return f"{row['start']} {row['duration']} {1}"
        return f"{row['start']:.2f} {row['duration']:.2f} {1}"

    # Create output directory if it doesn't exist
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Set file paths based on output directory
    if output_dir:
        firstnp_path = os.path.join(output_dir, "firstnp.txt")
        lastnp_path = os.path.join(output_dir, "lastnp.txt")
        probe_path = os.path.join(output_dir, "probe.txt")
    else:
        firstnp_path = "firstnp.txt"
        lastnp_path = "lastnp.txt"
        probe_path = "probe.txt"

    # Write the results to text files
    with open(firstnp_path, "w") as f:
        for row in first_np_before_p:
            f.write(format_row(row) + "\n")

    with open(lastnp_path, "w") as f:
        for row in last_np_before_p:
            f.write(format_row(row) + "\n")

    with open(probe_path, "w") as f:
        for row in p_trials:
            f.write(format_row(row) + "\n")

    print(f"Processed {file_path}")
    print(f"Created three text files in {output_dir or 'current directory'}:")
    print(f"  - {os.path.basename(firstnp_path)}")
    print(f"  - {os.path.basename(lastnp_path)}")
    print(f"  - {os.path.basename(probe_path)}")
    print(f"Found {len(p_trials)} probe trials, {len(first_np_before_p)} first NPs, and {len(last_np_before_p)} last NPs")