#!/bin/bash
# Wait for MongoDB to be fully ready, then initiate replica set if not already done
set -e

echo "[RS-INIT] Waiting for MongoDB to accept connections..."
until mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  sleep 1
done

echo "[RS-INIT] MongoDB is up. Checking replica set status..."
STATUS=$(mongosh --quiet --eval "try { rs.status().ok } catch(e) { 0 }")

if [ "$STATUS" = "1" ]; then
  echo "[RS-INIT] Replica set already initialized."
else
  echo "[RS-INIT] Initiating replica set rs0..."
  mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
  echo "[RS-INIT] Replica set initiated successfully."
fi
