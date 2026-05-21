#!/bin/bash
# Tạo nhiều database trong một Postgres container
# Đọc biến POSTGRES_MULTIPLE_DATABASES (phân cách bằng dấu phẩy)
# Ví dụ: POSTGRES_MULTIPLE_DATABASES=collector_db,airflow_db

set -e

function create_database() {
    local db=$1
    echo "📦 Tạo database: $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE $db'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
}

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "🛠  Khởi tạo nhiều database: $POSTGRES_MULTIPLE_DATABASES"
    for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
        create_database "$db"
    done
    echo "✅ Hoàn thành tạo databases"
fi
