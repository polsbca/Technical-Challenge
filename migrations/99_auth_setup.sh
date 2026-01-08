#!/bin/bash
# This script runs after PostgreSQL starts to configure authentication

# Update pg_hba.conf to allow connections from anywhere using md5 (simpler than scram-sha-256)
# Comment out the existing rules and add our own
sed -i 's/^host all all all scram-sha-256/host all all 0.0.0.0\/0 md5/' /var/lib/postgresql/data/pg_hba.conf
sed -i 's/^host replication all all scram-sha-256/host replication all 0.0.0.0\/0 md5/' /var/lib/postgresql/data/pg_hba.conf

# Reload PostgreSQL configuration
psql -U postgres -c "SELECT pg_reload_conf();" 2>/dev/null || true

echo "Authentication configuration updated"
