import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def detect_and_label_teleportations(csv_path):
    """
    Detects teleportation returns to specified starting positions and labels them in the CSV.
    
    Parameters:
    - csv_path: Path to the input CSV file
    - positions: List of tuples representing starting positions [(x1, z1), (x2, z2), ...]
    - output_csv_path: Path to save the labeled CSV (defaults to input_path with '_labeled' suffix)
    - distance_threshold: Minimum distance change to consider a "teleportation"
    
    Returns:
    - DataFrame with teleportation events labeled
    - Visualization of the trajectory and teleportation events
    """
    # Initializing variables
    distance_threshold = 5.0
    positions = [(36.52, 22), (0, -32)]

    # Read the CSV file - note the column names have leading spaces
    df = pd.read_csv(csv_path)
    
    # Create a backup of the original dataframe
    labeled_df = df.copy()
    
    # Create columns to track position differences between consecutive rows
    labeled_df['X_prev'] = labeled_df[' X'].shift(1)
    labeled_df['Z_prev'] = labeled_df[' Z'].shift(1)
    
    # Calculate Euclidean distance between consecutive positions
    labeled_df['position_change'] = np.sqrt(
        (labeled_df[' X'] - labeled_df['X_prev'])**2 + 
        (labeled_df[' Z'] - labeled_df['Z_prev'])**2
    )
    
    # Create new columns for teleportation detection
    labeled_df['is_teleport'] = False
    labeled_df['teleport_to'] = None
    
    # Additional column for internal tracking (won't be in final output)
    labeled_df['_first_teleport_to_position'] = False
    
    # Dictionary to track whether we've seen the first teleport to each position
    first_teleport_seen = {i: False for i in range(len(positions))}
    
    # Process each row (skip first row since it has no previous position)
    for idx, row in labeled_df.iloc[1:].iterrows():
        # Check if there was a significant position change (potential teleportation)
        if row['position_change'] >= distance_threshold:
            # Check if current position is close to any of the target positions
            for pos_idx, (target_x, target_z) in enumerate(positions):
                distance_to_target = np.sqrt((row[' X'] - target_x)**2 + (row[' Z'] - target_z)**2)
                tolerance = 1.0  # Small tolerance for exact position matching
                
                if distance_to_target <= tolerance:
                    # Mark this row as a teleportation
                    labeled_df.at[idx, 'is_teleport'] = True
                    labeled_df.at[idx, 'teleport_to'] = f"Target {pos_idx+1}: ({target_x}, {target_z})"
                    
                    # Check if this is the first teleport to this position (for internal use)
                    if not first_teleport_seen[pos_idx]:
                        labeled_df.at[idx, '_first_teleport_to_position'] = True
                        first_teleport_seen[pos_idx] = True
                    
                    break  # Only mark as teleporting to one position
    
    # Create a summary dataframe of teleportation events for visualization and reporting
    teleport_rows = labeled_df[labeled_df['is_teleport']]
    teleport_summary = teleport_rows[[' Cummulative_Time', ' X', ' Z', 'teleport_to', '_first_teleport_to_position']]
    
    # Plot results
    if not df.empty:
        plt.figure(figsize=(12, 8))
        
        # Plot all positions
        plt.scatter(df[' X'], df[' Z'], alpha=0.3, label='All positions')
        
        # Plot positions with lines connecting them to show movement path
        plt.plot(df[' X'], df[' Z'], 'b-', alpha=0.2)
        
        # Highlight teleportation events
        if not teleport_rows.empty:
            # Regular teleports
            regular_teleports = teleport_rows[~teleport_rows['_first_teleport_to_position']]
            if not regular_teleports.empty:
                plt.scatter(regular_teleports[' X'], regular_teleports[' Z'], 
                           c='red', s=100, label='Teleportation returns')
            
            # First teleports to each position (highlight differently)
            first_teleports = teleport_rows[teleport_rows['_first_teleport_to_position']]
            if not first_teleports.empty:
                plt.scatter(first_teleports[' X'], first_teleports[' Z'], 
                           c='orange', s=150, edgecolors='red', linewidths=2,
                           label='First teleport to position')
                
                # Add text labels for first teleports
                for _, event in first_teleports.iterrows():
                    plt.annotate(f"First teleport: t={event[' Cummulative_Time']:.2f}", 
                                xy=(event[' X'], event[' Z']),
                                xytext=(10, 10), textcoords='offset points',
                                bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.7))
            
            # Draw arrows for all teleportations
            for _, event in teleport_rows.iterrows():
                plt.arrow(event['X_prev'], event['Z_prev'], 
                         event[' X'] - event['X_prev'], event[' Z'] - event['Z_prev'],
                         color='red', width=0.1, head_width=0.5, alpha=0.7)
        
        # Mark target positions
        for i, (x, z) in enumerate(positions):
            plt.scatter([x], [z], c='green', s=200, marker='*', 
                       label=f'Target {i+1}: ({x}, {z})' if i == 0 else f'Target {i+1}: ({x}, {z})')
        
        plt.xlabel('X Position')
        plt.ylabel('Z Position')
        plt.title('Detection of Teleportation Returns to Starting Positions')
        plt.legend()
        plt.grid(True)
    
    # Remove the internal tracking column before saving
    labeled_df = labeled_df.drop(columns=['_first_teleport_to_position'])
    
    # Display summary of first teleports to each position
    first_teleports = teleport_rows[teleport_rows['_first_teleport_to_position']]
    if not first_teleports.empty:
        print("\nFirst teleportation to each position:")
        for _, row in first_teleports.iterrows():
            print(f"Time: {row[' Cummulative_Time']:.4f}, Position: {row['teleport_to']}")
    
    return labeled_df, teleport_summary