-- Script này chạy trước init-db.sql để đảm bảo airflow_db tồn tại
-- Postgres chạy các script trong /docker-entrypoint-initdb.d/ theo thứ tự alphabet

SELECT 'CREATE DATABASE airflow_db'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'airflow_db'
)\gexec
