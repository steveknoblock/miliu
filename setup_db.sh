#!/bin/bash
# =============================================================================
# Miliu — Local Database Setup Script
# Run once to create the database and user for local development.
# Usage: bash scripts/setup_db.sh
# =============================================================================

set -e  # Exit on any error

# ── Load .env if it exists ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    echo "→ Loading environment from .env"
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# ── Parse DATABASE_URL or use defaults ───────────────────────────────────────
# Expected format: postgresql+asyncpg://user:password@host:port/dbname
if [ -n "$DATABASE_URL" ]; then
    # Strip the driver prefix for psql compatibility
    CLEAN_URL="${DATABASE_URL/postgresql+asyncpg/postgresql}"

    DB_USER=$(echo "$CLEAN_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
    DB_PASS=$(echo "$CLEAN_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
    DB_HOST=$(echo "$CLEAN_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
    DB_PORT=$(echo "$CLEAN_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    DB_NAME=$(echo "$CLEAN_URL" | sed -n 's|.*/\([^?]*\)|\1|p')
else
    DB_USER="${DB_USER:-miliu_user}"
    DB_PASS="${DB_PASS:-devpassword}"
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    DB_NAME="${DB_NAME:-miliu}"
fi

echo ""
echo "Database config:"
echo "  Host:     $DB_HOST:$DB_PORT"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo ""

# ── Helper to run SQL as postgres superuser ───────────────────────────────────
run_as_postgres() {
    if command -v sudo &>/dev/null; then
        sudo -u postgres psql "$@"
    else
        su -c "psql $*" postgres
    fi
}

# ── Create user if not exists ─────────────────────────────────────────────────
echo "→ Creating user '$DB_USER'..."
run_as_postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 \
    && echo "  User already exists, skipping." \
    || run_as_postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

# ── Create database if not exists ────────────────────────────────────────────
echo "→ Creating database '$DB_NAME'..."
run_as_postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
    && echo "  Database already exists, skipping." \
    || run_as_postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# ── Grant privileges ──────────────────────────────────────────────────────────
echo "→ Granting privileges..."
run_as_postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
run_as_postgres -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;"
run_as_postgres -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;"
run_as_postgres -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO $DB_USER;"
run_as_postgres -d "$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;"
run_as_postgres -d "$DB_NAME" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;"

echo ""
echo "✓ Database setup complete."
echo ""
echo "Next steps:"
echo "  1. cp .env.example .env  (if not done)"
echo "  2. alembic upgrade head  (apply schema via migrations)"
echo ""
