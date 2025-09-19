#!/usr/bin/env python3
"""
Console Log Checker for Kaggle Notebook
Queries the Neon database to retrieve console logs from Cell 0 execution
"""

import psycopg2
import os
import sys
from datetime import datetime

def get_neon_credentials():
    """Get Neon database credentials from environment or prompt"""
    # Try to get from environment first
    credentials = {
        'host': os.getenv('NEON_HOST'),
        'database': os.getenv('NEON_DATABASE'),
        'user': os.getenv('NEON_USER'),
        'password': os.getenv('NEON_PASSWORD'),
        'port': 5432,
        'sslmode': 'require'
    }

    # If not in environment, prompt for them
    missing = [key for key, value in credentials.items() if not value and key != 'port' and key != 'sslmode']

    if missing:
        print("🔑 Neon database credentials needed:")
        for key in missing:
            credentials[key] = input(f"Enter {key}: ")

    return credentials

def query_console_logs(credentials, cell_numbers=None, limit=None):
    """Query console logs from Neon database"""
    try:
        # Connect to database
        conn = psycopg2.connect(**credentials)
        cursor = conn.cursor()

        # Build query
        base_query = """
        SELECT
            id,
            cell_number,
            console_output,
            created_at
        FROM core.console_logs
        """

        conditions = []
        params = []

        if cell_numbers:
            placeholders = ','.join(['%s'] * len(cell_numbers))
            conditions.append(f"cell_number IN ({placeholders})")
            params.extend(cell_numbers)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        base_query += " ORDER BY created_at ASC"

        if limit:
            base_query += f" LIMIT {limit}"

        print(f"🔍 Executing query: {base_query}")
        print(f"📊 Parameters: {params}")

        cursor.execute(base_query, params)
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return results

    except Exception as e:
        print(f"❌ Database query failed: {e}")
        return None

def display_console_logs(logs):
    """Display console logs in a readable format"""
    if not logs:
        print("📭 No console logs found")
        return

    print(f"\n📊 Found {len(logs)} console log entries:")
    print("=" * 80)

    current_cell = None

    for log_id, cell_number, output, timestamp in logs:
        # Show cell header when switching cells
        if current_cell != cell_number:
            current_cell = cell_number
            print(f"\n🔥 CELL {cell_number} LOGS:")
            print("-" * 50)

        # Format timestamp
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%H:%M:%S")
        else:
            time_str = str(timestamp)

        # Display log entry
        print(f"[{time_str}] {output}")

    print("=" * 80)

def main():
    """Main function to check console logs"""
    print("🔍 Console Log Checker for Kaggle Notebook")
    print("=" * 50)

    # Get database credentials
    credentials = get_neon_credentials()

    # Query for Cell -1 and Cell 0 logs (our setup and package installation)
    cell_numbers = [-1, 0]
    print(f"\n🎯 Checking logs for cells: {cell_numbers}")

    # Query database
    logs = query_console_logs(credentials, cell_numbers=cell_numbers, limit=1000)

    if logs is not None:
        display_console_logs(logs)

        # Summary
        cell_counts = {}
        for log_id, cell_number, output, timestamp in logs:
            cell_counts[cell_number] = cell_counts.get(cell_number, 0) + 1

        print(f"\n📈 Summary:")
        for cell, count in sorted(cell_counts.items()):
            print(f"   Cell {cell}: {count} log entries")

    print("\n✅ Console log check complete")

if __name__ == "__main__":
    main()