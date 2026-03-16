-- Initial database schema with tracking table
-- Note: tracks, albums, and related tables are created by utils/database.py
-- This migration only tracks schema versions for future migrations

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
