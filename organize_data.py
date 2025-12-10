#!/usr/bin/env python3

import os
import glob
import shutil
import re

def main():
    # Create folders NAV066 through NAV081
    print("Creating folders NAV066 through NAV081...")
    for i in range(66, 82):
        folder_name = f"NAV{i:03d}"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            print(f"Created folder: {folder_name}")
        else:
            print(f"Folder already exists: {folder_name}")
    
    # Get list of all files in current directory
    all_files = [f for f in os.listdir('.') if os.path.isfile(f)]
    
    # Pattern to match NAV followed by 3 digits
    nav_pattern = re.compile(r'(NAV\d{3})')
    
    # Track how many files were moved
    moved_count = 0
    
    print("\nMoving files to corresponding folders...")
    
    # Check each file to see if it contains a NAV identifier
    for file in all_files:
        # Find all NAV patterns in the filename
        matches = nav_pattern.findall(file)
        
        # Move file to corresponding folder if there's a match
        for nav_id in matches:
            # Make sure the folder exists and this isn't the script itself
            if os.path.isdir(nav_id) and file != os.path.basename(__file__):
                try:
                    # Ensure we don't move files that are already in correct folders
                    if not file.startswith(f"{nav_id}/"):
                        shutil.move(file, os.path.join(nav_id, file))
                        print(f"Moved: {file} -> {nav_id}/")
                        moved_count += 1
                        # Break after first match to avoid trying to move the same file multiple times
                        break
                except Exception as e:
                    print(f"Error moving {file}: {e}")
    
    print(f"\nCompleted! Created folders NAV066 through NAV081 and moved {moved_count} files.")

if __name__ == "__main__":
    main()