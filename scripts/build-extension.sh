#!/bin/bash
set -e

echo "Building Chrome Extension zip..."
cd chrome-extension
# Remove any existing zip
rm -f ../llm-radar-extension.zip
# Zip the necessary files, excluding hidden files or unwanted directories
zip -r ../llm-radar-extension.zip . -x ".*" -x "__MACOSX" -x "store-assets/*"
cd ..
echo "Done! The extension is packed at llm-radar-extension.zip"
