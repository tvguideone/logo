#!/bin/bash

# Directory to store downloaded images
DOWNLOAD_DIR="downloaded_images"
mkdir -p $DOWNLOAD_DIR

# Download images
for id in {1..10000}; do
    url="https://static.quickgrow.net/football/leagues/${id}.png"
    output="${DOWNLOAD_DIR}/${id}.png"
    
    # Use curl to download the image and check if it exists
    curl -s -f -o $output $url
    if [ $? -ne 0 ]; then
        echo "Image with id ${id} does not exist, skipping..."
        rm -f $output
    else
        echo "Downloaded image with id ${id}"
    fi
done

# Archive the downloaded images into a zip file
zip -r downloaded_images.zip $DOWNLOAD_DIR
