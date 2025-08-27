-- Create kaggle_logs table in core schema for tracking Kaggle notebook executions
-- Run this in Neon database: BizIntelSmartReach

-- Create table if not exists
CREATE TABLE IF NOT EXISTS core.kaggle_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(50) NOT NULL,
    session_name VARCHAR(100),
    cell_number INTEGER,
    message TEXT NOT NULL,
    data JSONB,
    execution_time FLOAT,
    success BOOLEAN,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_kaggle_logs_session ON core.kaggle_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_kaggle_logs_timestamp ON core.kaggle_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_kaggle_logs_success ON core.kaggle_logs(success);
CREATE INDEX IF NOT EXISTS idx_kaggle_logs_session_name ON core.kaggle_logs(session_name);

-- Create a view for easy session summaries
CREATE OR REPLACE VIEW core.kaggle_session_summary AS
SELECT 
    session_id,
    session_name,
    MIN(timestamp) as session_start,
    MAX(timestamp) as session_end,
    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/60 as duration_minutes,
    COUNT(DISTINCT cell_number) as cells_executed,
    COUNT(CASE WHEN success = false THEN 1 END) as error_count,
    COUNT(CASE WHEN execution_time > 10 THEN 1 END) as slow_cells,
    AVG(execution_time) as avg_execution_time,
    MAX(execution_time) as max_execution_time
FROM core.kaggle_logs
WHERE cell_number IS NOT NULL
GROUP BY session_id, session_name
ORDER BY session_start DESC;

-- Create a view for recent errors
CREATE OR REPLACE VIEW core.kaggle_recent_errors AS
SELECT 
    timestamp,
    session_name,
    cell_number,
    message,
    error,
    data->>'suggested_fix' as suggested_fix
FROM core.kaggle_logs
WHERE success = false OR error IS NOT NULL
ORDER BY timestamp DESC
LIMIT 50;

-- Create a function to get session details
CREATE OR REPLACE FUNCTION core.get_kaggle_session_details(p_session_id VARCHAR)
RETURNS TABLE (
    cell_number INTEGER,
    timestamp TIMESTAMP,
    message TEXT,
    execution_time FLOAT,
    success BOOLEAN,
    cell_type TEXT,
    insights JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        kl.cell_number,
        kl.timestamp,
        kl.message,
        kl.execution_time,
        kl.success,
        kl.data->>'cell_type' as cell_type,
        kl.data->'insights' as insights
    FROM core.kaggle_logs kl
    WHERE kl.session_id = p_session_id
    AND kl.cell_number IS NOT NULL
    ORDER BY kl.cell_number;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed)
GRANT ALL ON TABLE core.kaggle_logs TO neondb_owner;
GRANT ALL ON SEQUENCE core.kaggle_logs_id_seq TO neondb_owner;

-- Add helpful comments
COMMENT ON TABLE core.kaggle_logs IS 'Automatic logging from Kaggle notebook executions';
COMMENT ON COLUMN core.kaggle_logs.session_id IS 'Unique identifier for each Kaggle session';
COMMENT ON COLUMN core.kaggle_logs.session_name IS 'User-provided name for the session';
COMMENT ON COLUMN core.kaggle_logs.data IS 'JSON data containing structured information from cell execution';
COMMENT ON COLUMN core.kaggle_logs.execution_time IS 'Time taken to execute the cell in seconds';

-- Sample queries for Claude to use:

-- Get latest session
-- SELECT * FROM core.kaggle_session_summary LIMIT 1;

-- Get errors from latest session
-- SELECT * FROM core.kaggle_recent_errors WHERE session_name LIKE '%patent%';

-- Get detailed cell execution for a session
-- SELECT * FROM core.get_kaggle_session_details('kaggle_20240827_054500');