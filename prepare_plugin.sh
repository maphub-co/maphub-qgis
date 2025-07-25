#!/bin/bash

# Create a copy of the project folder in the parent directory with the name "maphub"
cp -r . "../maphub"

# Remove unnecessary folders and files
find "../maphub" -name "__pycache__" -type d -exec rm -rf {} +
rm -rf "../maphub/.git" "../maphub/.junie" "../maphub/.idea"
rm -f "../maphub/$(basename "$0")"  # Remove this script from the copy

# Compress the folder into a zip file in the parent directory
cd ..
zip -r "maphub.zip" "maphub"

# Remove the temporary copy
rm -rf "maphub"

echo "Plugin package created: maphub.zip"