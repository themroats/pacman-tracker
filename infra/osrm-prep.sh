#!/bin/sh
# OSRM data preparation script — runs inside the OSRM container.
# Expects /data to be a mounted volume with washington-latest.osm.pbf already present.
# The download step is handled separately (Alpine container or local Docker Compose).
#
# Local testing:
#   # Step 1: Download (if needed)
#   docker run --rm -v osrm-test-data:/data alpine:3.20 sh -c \
#     "apk add --no-cache wget && wget -O /data/washington-latest.osm.pbf https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf"
#   # Step 2: Extract/partition/customize
#   docker run --rm -v osrm-test-data:/data -v ${PWD}/infra:/scripts \
#     osrm/osrm-backend:latest /bin/sh /scripts/osrm-prep.sh
set -e

echo "OSRM Data Preparation starting..."

if [ ! -f /data/washington-latest.osm.pbf ]; then
  echo "ERROR: /data/washington-latest.osm.pbf not found."
  echo "Download it first (see script header for instructions)."
  exit 1
fi

# Extract, partition, customize for foot routing
if [ ! -f /data/washington-latest.osrm ]; then
  echo "Extracting with foot profile..."
  osrm-extract -p /opt/foot.lua /data/washington-latest.osm.pbf
  echo "Partitioning..."
  osrm-partition /data/washington-latest.osrm
  echo "Customizing..."
  osrm-customize /data/washington-latest.osrm
else
  echo "OSRM data already prepared, skipping."
fi

echo "OSRM Data Preparation Complete."
