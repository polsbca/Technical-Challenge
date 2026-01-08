#!/bin/bash
# Initialize PostgreSQL authentication for remote connections
# This file is executed by docker-entrypoint-initdb.d after database creation

set -e

echo "Configuring PostgreSQL for remote authentication..."

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
            echo "PostgreSQL is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    
    echo "PostgreSQL failed to start after $max_attempts attempts"
    return 1
}

# Wait for the database to be ready
wait_for_postgres

# Update pg_hba.conf to allow remote connections
# We need to do this BEFORE we try to reload
cat > /tmp/pg_hba.conf.append << 'HBAEOF'

# Remote connections configuration (added by init script)
# Allow TCP/IP connections from any IP with password authentication
host    all             all             0.0.0.0/0               md5
host    all             all             ::/0                    md5
HBAEOF

# Check if these rules already exist
if ! grep -q "Remote connections configuration" /var/lib/postgresql/data/pg_hba.conf; then
    echo "Adding remote connection rules to pg_hba.conf..."
    cat /tmp/pg_hba.conf.append >> /var/lib/postgresql/data/pg_hba.conf
    
    # Signal PostgreSQL to reload
    # The '-S' flag allows pg_ctl to work even if the postmaster.opts file doesn't exist yet
    pg_ctl reload -D /var/lib/postgresql/data 2>/dev/null || {
        # If reload fails, the settings will take effect on next restart
        echo "Could not reload pg_hba.conf immediately (will be applied on next restart)"
    }
else
    echo "Remote connection rules already configured"
fi

echo "PostgreSQL authentication configuration complete"
