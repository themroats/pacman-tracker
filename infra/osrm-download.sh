#!/bin/sh
# Download Washington state OSM data.
# Works in Alpine (with wget) or any image with curl.
set -e

if [ -f /data/washington-latest.osm.pbf ]; then
  echo "OSM data already downloaded, skipping."
  exit 0
fi

echo "Downloading Washington state OSM data..."
if command -v curl > /dev/null 2>&1; then
  curl -fSL -o /data/washington-latest.osm.pbf \
    https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf
elif command -v wget > /dev/null 2>&1; then
  wget -O /data/washington-latest.osm.pbf \
    https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf
else
  echo "ERROR: Neither curl nor wget found." >&2
  exit 1
fi
echo "Download complete."
