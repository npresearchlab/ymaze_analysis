import pandas as pd

def extract_teleport_timestamps(df):
    
    # Initialize dictionaries to store start and end timestamps
    trials = {}
    current_trials = {}
    current_env = None
    
    # Process each row in the dataframe
    for index, row in df.iterrows():
        # Get environment info
        env = row['Environment']
        if not pd.isna(env):
            current_env = env
            
        teleport_type = row['teleport_type']
        timestamp = row[' Cummulative_Time']
        
        # Skip if teleport_type is NaN or empty
        if pd.isna(teleport_type) or teleport_type == '':
            continue
        
        # Check if this is a start marker (np1, np2, p, etc.)
        if teleport_type.endswith('end'):
            # This is an end marker
            base_type = teleport_type.replace('end', '')
            
            # If we have a corresponding start, record the pair
            if base_type in current_trials:
                start_time = current_trials[base_type]['time']
                start_env = current_trials[base_type]['env']
                
                if base_type not in trials:
                    trials[base_type] = []
                
                trials[base_type].append({
                    'env': start_env,
                    'trial': base_type,
                    'start': start_time,
                    'end': timestamp,
                    'duration': timestamp - start_time
                })
                
                # Remove from current trials
                del current_trials[base_type]
        else:
            # This is a start marker
            current_trials[teleport_type] = {
                'time': timestamp,
                'env': current_env
            }
    
    # Create a list to hold all results
    results = []
    for trial_type, timestamps in trials.items():
        for trial in timestamps:
            results.append(trial)
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Reorder columns if needed
    ordered_cols = ['env', 'trial', 'start', 'end', 'duration']
    results_df = results_df[ordered_cols]
    
    # Sort by start time to ensure trials are in chronological order
    results_df = results_df.sort_values('start')
    
    # Find the initial timestamp (minimum start time)
    initial_timestamp = results_df['start'].min()
    
    # Adjust all timestamps relative to the initial timestamp
    results_df['end'] = results_df['end'] - initial_timestamp
    results_df['start'] = results_df['start'] - initial_timestamp
    
    # Duration should remain the same as it's a difference between end and start
    # results_df['duration'] = results_df['end'] - results_df['start']
    
    return results_df