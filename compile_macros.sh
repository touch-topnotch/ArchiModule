#!/bin/bash

# Define the source and destination files
SOURCE_FILE="ArchiContextWindow.py"
DESTINATION_FILE="ArchiContextWindow.FCMacro"

# Check if the source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Source file $SOURCE_FILE does not exist."
    exit 1
fi

# Copy the contents of the source file to the destination file
cat "$SOURCE_FILE" > "$DESTINATION_FILE"

echo "Contents of $SOURCE_FILE have been copied to $DESTINATION_FILE."