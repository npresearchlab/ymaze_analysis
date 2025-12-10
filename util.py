import os
from pathlib import Path

def save_csv(df, output_path, tag, sub=None): 
    """
    Save dataframe to CSV with optional subject-specific subfolder
    
    Parameters:
    - df: DataFrame to save
    - output_path: Base output directory path
    - tag: File identifier to append to filename
    - sub: Optional subject ID. If provided, creates a subject subfolder
    """
    if sub:
        # Save to subject-specific folder
        sub_dir = os.path.join(output_path, sub)
        os.makedirs(sub_dir, exist_ok=True)  # Create subject directory if it doesn't exist
        csv_path = os.path.join(sub_dir, f"{sub}_{tag}.csv")
    else:
        # Save directly to output path
        os.makedirs(output_path, exist_ok=True)  # Create output directory if it doesn't exist
        csv_path = os.path.join(output_path, f"{tag}.csv")
    
    df.to_csv(csv_path, index=False)
    return csv_path  # Return the path for reference