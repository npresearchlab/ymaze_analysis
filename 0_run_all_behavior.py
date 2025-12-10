import os
import subprocess
from pathlib import Path

from detect_teleport import detect_and_label_teleportations
from label_trials import label_teleportations
from util import save_csv
from collapse_labels import extract_teleport_timestamps
from create_timing import process_trial_data

# Initialize variables
data_path = "/Volumes/YB_Drive/YB/1_data/behavior/"
output_path = "/Volumes/YB_Drive/YB/2_analysis/behavior/"
code_path = "/Volumes/YB_Drive/YB/0_tools/behavior/"

def main():
    # Validate paths
    if not os.path.isdir(data_path):
        print("Error: The data filepath is not a valid directory.")
        return

    if not os.path.isdir(output_path):
        print("Error: The output filepath is not a valid directory.")
        return

    # Get list of actual folders (excluding .DS_Store and other hidden files)
    all_items = os.listdir(data_path)
    print(f"All items in directory: {all_items}")
    
    folders = []
    for item in all_items:
        item_path = os.path.join(data_path, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            folders.append(item)
    
    print(f"Folders to process: {folders}")
    
    # Counter for subject numbering - explicitly starting at 1
    subject_counter = 1
    
    # Iterate through each valid folder
    for folder in folders:
        folder_path = os.path.join(data_path, folder)
        
        # Generate new folder name with sequential numbering
        new_folder_name = f"sub-{subject_counter:02d}"  # Format: sub-01, sub-02, etc.
        print(f"Assigning {folder} as {new_folder_name}")
        
        # Create subject-specific analysis folder with new naming
        sub_folder_path = Path(os.path.join(output_path, new_folder_name))
        
        os.chdir(output_path)
        
        # (If it already exists, it won't create a new one)
        sub_folder_path.mkdir(exist_ok=True)
        
        os.chdir(folder_path)
        
        # List all files in the current directory
        files_in_directory = os.listdir(folder_path)
        
        # Find the first file that contains "Coordinates" in its name
        coordinate_file = next((file for file in files_in_directory if "Coordinates" in file), None)
        
        # Store the filename if found
        if coordinate_file:
            print(f"Processing {folder} as {new_folder_name}. Found file:", coordinate_file)
        else:
            print(f"Processing {folder} as {new_folder_name}. No file containing 'Coordinates' found.")
            # Still increment the counter even if no coordinate file found
            subject_counter += 1
            continue  # Skip to next folder if no coordinate file found
        
        # Run detect_teleport script
        labeled_df, teleport_events = detect_and_label_teleportations(coordinate_file)
        
        # Run label_trials script
        labeled2_df = label_teleportations(labeled_df)
        save_csv(labeled2_df, sub_folder_path, f"{new_folder_name}_temp2")
        
        # Run collapse_labels script
        labeled3_df = extract_teleport_timestamps(labeled2_df)
        save_csv(labeled3_df, sub_folder_path, f"{new_folder_name}_temp3")
        
        # Save output to subject-specific folder with new naming
        os.chdir(output_path)
        save_csv(labeled3_df, sub_folder_path, f"{new_folder_name}_labeled_final")
        
        # Run create_timing script
        fsl_timing_df = process_trial_data(os.path.join(sub_folder_path, f"{new_folder_name}_labeled_final.csv"), os.path.join(sub_folder_path))
        
        # Increment the counter for the next folder
        subject_counter += 1

if __name__ == "__main__":
    main()