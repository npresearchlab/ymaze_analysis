import pandas as pd
import numpy as np

def label_teleportations(df):
    
    # Add a new column 'teleport_type' with default value NaN
    df['teleport_type'] = pd.NA
    
    # Label the first row as 'np1'
    if len(df) > 0:
        df.loc[0, 'teleport_type'] = 'np1'
    
    # Get unique environments
    environments = df['Environment'].unique()
    
    # First pass: Label all teleportations with basic labels
    # Keep track of whether we're in the first environment
    first_env = True
    
    for env in environments:
        # Get teleportation rows for this environment
        env_teleports = df[(df['Environment'] == env) & (df['is_teleport'] == True)]
        
        if len(env_teleports) > 0:
            # Get the index of the last teleportation for this environment
            last_teleport_index = env_teleports.index[-1]
            
            # Initialize counter for non-probe teleportations
            # For first environment, start at 2 (since np1 is used for first row)
            # For other environments, start at 1
            np_counter = 2 if first_env else 1
            
            # Process each teleportation in this environment
            for idx in env_teleports.index:
                if idx == last_teleport_index:
                    # Label last teleportation as "p"
                    df.loc[idx, 'teleport_type'] = 'p'
                else:
                    # Label other teleportations as "np2", "np3", etc. for first env,
                    # or "np1", "np2", etc. for other envs
                    df.loc[idx, 'teleport_type'] = f'np{np_counter}'
                    np_counter += 1
        
        # Mark that we've processed the first environment
        first_env = False
    
    # Second pass: Process each environment separately for end labels
    for env in environments:
        # Get all teleportation rows for this environment in order
        env_teleports = df[(df['Environment'] == env) & (df['is_teleport'] == True)].sort_index()
        
        # Skip if no teleportations
        if len(env_teleports) == 0:
            continue
        
        # For each teleportation
        for i in range(len(env_teleports)):
            current_idx = env_teleports.index[i]
            
            # Skip if it's the first row (already labeled as np1)
            if current_idx == 0:
                continue
            
            # Determine previous label
            if i == 0:
                # If this is the first teleportation in this environment
                if env == environments[0]:
                    # For first environment, use 'np1' as the previous label (from first row)
                    previous_label = 'np1'
                else:
                    # For other environments, find the last teleportation in the previous environment
                    prev_env = environments[np.where(environments == env)[0][0] - 1]
                    prev_env_teleports = df[(df['Environment'] == prev_env) & (df['is_teleport'] == True)]
                    
                    if len(prev_env_teleports) > 0:
                        # Use the label from the last teleportation in previous environment
                        prev_env_last_idx = prev_env_teleports.index[-1]
                        previous_label = df.loc[prev_env_last_idx, 'teleport_type']
                    else:
                        # If no teleportations in previous environment, use default
                        previous_label = 'np1'
            else:
                # Otherwise use the label from the previous teleportation in this environment
                previous_idx = env_teleports.index[i-1]
                previous_label = df.loc[previous_idx, 'teleport_type']
            
            # Get the coordinates from the row right before the current teleportation
            pre_teleport_idx = current_idx - 1
            pre_teleport_x = df.loc[pre_teleport_idx, ' X']
            pre_teleport_z = df.loc[pre_teleport_idx, ' Z']
            
            # Look backward to find where this chunk of coordinates began
            chunk_start_idx = pre_teleport_idx
            
            # Determine how far back to search
            if i == 0:
                # For first teleportation in environment, search back to previous environment's last teleport
                if env == environments[0]:
                    search_back_to = 0
                else:
                    prev_env = environments[np.where(environments == env)[0][0] - 1]
                    prev_env_teleports = df[(df['Environment'] == prev_env) & (df['is_teleport'] == True)]
                    
                    if len(prev_env_teleports) > 0:
                        search_back_to = prev_env_teleports.index[-1]
                    else:
                        search_back_to = 0
            else:
                # For others, search back to previous teleportation in this environment
                search_back_to = env_teleports.index[i-1]
            
            # Iterate backwards until we find a change in coordinates
            for back_idx in range(pre_teleport_idx-1, search_back_to, -1):
                # If coordinates don't match, we've found the start of the repeating chunk
                if df.loc[back_idx, ' X'] != pre_teleport_x or df.loc[back_idx, ' Z'] != pre_teleport_z:
                    chunk_start_idx = back_idx + 1
                    break
            
            # Label the first row of the repeating chunk with the appropriate end label
            if chunk_start_idx != pre_teleport_idx and chunk_start_idx != 0:  # Skip if it's first row
                df.loc[chunk_start_idx, 'teleport_type'] = f"{previous_label}end"
        
        # Handle the last teleportation in the environment
        last_teleport_idx = env_teleports.index[-1]
        last_label = df.loc[last_teleport_idx, 'teleport_type']
        
        # Skip if it's the last row in the dataframe
        if last_teleport_idx < len(df) - 1:
            # Look for repeating coordinates after the last teleportation
            post_teleport_idx = last_teleport_idx + 1
            post_teleport_x = df.loc[post_teleport_idx, ' X']
            post_teleport_z = df.loc[post_teleport_idx, ' Z']
            
            # Look forward until coordinates change or end of data
            chunk_end_idx = post_teleport_idx
            for forward_idx in range(post_teleport_idx+1, len(df)):
                # Fixed a potential bug in the original code - using 'Z' instead of ' Z'
                if df.loc[forward_idx, ' X'] != post_teleport_x or df.loc[forward_idx, ' Z'] != post_teleport_z:
                    break
                chunk_end_idx = forward_idx
            
            # If we found a repeating chunk, label its beginning
            if chunk_end_idx > post_teleport_idx:
                df.loc[post_teleport_idx, 'teleport_type'] = f"{last_label}end"
    
    # Third pass: Remove "pend" labels that immediately follow "p" labels
    removed_pend_count = 0
    for i in range(len(df) - 1):
        # Check if current row has a teleport_type value
        if pd.notna(df.loc[i, 'teleport_type']):
            # Check if current row is a "p" label
            if df.loc[i, 'teleport_type'] == 'p':
                # Check if next row has a teleport_type value
                if pd.notna(df.loc[i+1, 'teleport_type']):
                    # Check if next row is a "pend" label
                    if df.loc[i+1, 'teleport_type'] == 'pend':
                        # Remove the "pend" label
                        df.loc[i+1, 'teleport_type'] = pd.NA
                        removed_pend_count += 1
    
    # NEW FUNCTIONALITY: Label the very last row in the dataframe as "pend"
    if len(df) > 0:
        last_row_idx = len(df) - 1
        df.loc[last_row_idx, 'teleport_type'] = 'pend'
    
    # Print summary
    teleport_count = len(df[df['is_teleport'] == True])
    probe_count = len(df[df['teleport_type'].fillna('').astype(str) == 'p'])
    np_count = len(df[df['teleport_type'].fillna('').astype(str).str.startswith('np') & 
                     ~df['teleport_type'].fillna('').astype(str).str.contains('end')])
    end_count = len(df[df['teleport_type'].fillna('').astype(str).str.contains('end')])
    np1end_count = len(df[df['teleport_type'].fillna('').astype(str) == 'np1end'])
    pend_count = len(df[df['teleport_type'].fillna('').astype(str) == 'pend'])
    
    print(f"Processed {teleport_count} teleportations across {len(environments)} environments")
    print(f"Labeled first row as 'np1'")
    print(f"Labeled {probe_count} as 'p' and {np_count-1} other teleportations with numbered 'np' labels")
    print(f"Found and labeled {end_count} chunk endpoints, including {np1end_count} as 'np1end' and {pend_count} as 'pend'")
    print(f"Non-probe counter started at 2 for first environment, and at 1 for all other environments")
    print(f"Removed {removed_pend_count} 'pend' labels that immediately followed 'p' labels")
    print(f"Added 'pend' label to the very last row of the dataframe")

    return df