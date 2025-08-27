#!/bin/bash

# =====================================================
# Company Deletion Script for SmartReach BizIntel
# =====================================================
# This script provides easy ways to delete company data
# from the database while handling all foreign key constraints
# =====================================================

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env file if it exists
if [ -f "$PROJECT_ROOT/config/.env" ]; then
    export $(cat "$PROJECT_ROOT/config/.env" | grep -v '^#' | xargs)
fi

# Database connection details
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-smartreachbizintel}"
DB_USER="${DB_USER:-srbiuser}"
DB_PASSWORD="${DB_PASSWORD:-SRBI_dev_2025}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run SQL commands
run_sql() {
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "$1"
}

# Function to run SQL file
run_sql_file() {
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f "$1"
}

# Function to display usage
usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  delete <domain1> [domain2] ...  Delete specific companies"
    echo "  delete-pattern <pattern>        Delete companies matching pattern (e.g., '%test%')"
    echo "  wipe-all                        Delete ALL companies (requires confirmation)"
    echo "  list                            List all companies in database"
    echo "  preview <domain>                Preview what would be deleted (dry run)"
    echo "  setup                           Set up deletion functions in database"
    echo "  help                            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 delete apple.com google.com"
    echo "  $0 delete-pattern '%test%'"
    echo "  $0 preview apple.com"
    echo "  $0 wipe-all"
}

# Main script logic
case "$1" in
    setup)
        echo -e "${YELLOW}Setting up deletion functions...${NC}"
        run_sql_file "$SCRIPT_DIR/SQL/delete_companies.sql"
        echo -e "${GREEN}Deletion functions installed successfully!${NC}"
        ;;
    
    delete)
        shift
        if [ $# -eq 0 ]; then
            echo -e "${RED}Error: No companies specified${NC}"
            echo "Usage: $0 delete <domain1> [domain2] ..."
            exit 1
        fi
        
        # Build array of domains
        domains=""
        for domain in "$@"; do
            if [ -z "$domains" ]; then
                domains="'$domain'"
            else
                domains="$domains, '$domain'"
            fi
        done
        
        echo -e "${YELLOW}Deleting companies: $@${NC}"
        run_sql "SELECT * FROM delete_companies(ARRAY[$domains]);"
        echo -e "${GREEN}Deletion complete!${NC}"
        ;;
    
    delete-pattern)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: No pattern specified${NC}"
            echo "Usage: $0 delete-pattern <pattern>"
            exit 1
        fi
        
        echo -e "${YELLOW}Deleting companies matching pattern: $2${NC}"
        run_sql "SELECT * FROM delete_companies(
            ARRAY(SELECT domain FROM core.companies WHERE domain LIKE '$2')
        );"
        echo -e "${GREEN}Deletion complete!${NC}"
        ;;
    
    wipe-all)
        echo -e "${RED}WARNING: This will delete ALL company data from the database!${NC}"
        echo -n "Are you sure? Type 'YES' to confirm: "
        read confirmation
        
        if [ "$confirmation" = "YES" ]; then
            echo -e "${YELLOW}Wiping all company data...${NC}"
            run_sql "SELECT * FROM wipe_all_company_data(TRUE);"
            echo -e "${GREEN}All company data has been deleted!${NC}"
        else
            echo "Cancelled."
        fi
        ;;
    
    list)
        echo -e "${YELLOW}Companies in database:${NC}"
        run_sql "SELECT domain, 
                 COALESCE(name, 'N/A') as name,
                 COALESCE(ticker, 'N/A') as ticker,
                 COALESCE(twitter_handle, 'N/A') as twitter,
                 COALESCE(twitter_status, 'pending') as status,
                 created_at::date as added
                 FROM core.companies 
                 ORDER BY domain;"
        ;;
    
    preview)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: No company specified${NC}"
            echo "Usage: $0 preview <domain>"
            exit 1
        fi
        
        echo -e "${YELLOW}Preview mode - showing what would be deleted for: $2${NC}"
        run_sql "BEGIN; SELECT * FROM delete_companies(ARRAY['$2']); ROLLBACK;"
        echo -e "${GREEN}This was a preview - no data was actually deleted${NC}"
        ;;
    
    help|--help|-h)
        usage
        ;;
    
    *)
        echo -e "${RED}Error: Unknown option '$1'${NC}"
        usage
        exit 1
        ;;
esac