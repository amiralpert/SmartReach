#!/usr/bin/env python3
"""
Apollo Enrichment Service for SmartReach BizIntel
Monitors companies table for new domains and enriches with Apollo.io API data
"""

import os
import psycopg2
import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from BizIntel config
config_path = Path(__file__).parent.parent.parent / 'config' / '.env'
load_dotenv(config_path)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApolloEnrichmentService:
    """
    Service to fetch organization data from Apollo.io API and enrich companies table
    """
    
    def __init__(self, apollo_api_key: str = None):
        """
        Initialize Apollo enrichment service
        
        Args:
            apollo_api_key: Apollo.io API key (or set APOLLO_API_KEY env var)
        """
        self.apollo_api_key = apollo_api_key or os.getenv('APOLLO_API_KEY')
        if not self.apollo_api_key:
            raise ValueError("Apollo API key required. Set APOLLO_API_KEY environment variable.")
        
        # Database connection
        self.conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=5432,
            database=os.getenv('DB_NAME', 'smartreachbizintel'),
            user=os.getenv('DB_USER', 'srbiuser'),
            password=os.getenv('DB_PASSWORD', 'SRBI_dev_2025')
        )
        self.conn.autocommit = False
        
        # Apollo API endpoint
        self.apollo_base_url = 'https://api.apollo.io/api/v1'
        
        # Rate limiting
        self.requests_per_minute = 50
        self.last_request_time = 0
        self.request_delay = 60 / self.requests_per_minute
    
    def get_new_domains(self, limit: int = 10) -> List[tuple]:
        """
        Get domains with NULL status (new entries needing Apollo data)
        
        Args:
            limit: Maximum number of domains to process
            
        Returns:
            List of (id, domain) tuples
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT id, domain 
                FROM companies 
                WHERE status IS NULL
                ORDER BY created_at ASC
                LIMIT %s
            """, (limit,))
            
            domains = cursor.fetchall()
            logger.info(f"Found {len(domains)} new domains to process")
            return domains
            
        finally:
            cursor.close()
    
    def fetch_apollo_organization(self, domain: str) -> Optional[Dict]:
        """
        Fetch organization data from Apollo.io API
        
        Args:
            domain: Company domain to search for
            
        Returns:
            Organization data dict or None if not found
        """
        # Rate limiting
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        
        headers = {
            'X-Api-Key': self.apollo_api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json',
            'Cache-Control': 'no-cache'
        }
        
        try:
            logger.info(f"Fetching Apollo data for domain: {domain}")
            # Use enrich endpoint with domain as query parameter
            response = requests.get(
                f'{self.apollo_base_url}/organizations/enrich',
                headers=headers,
                params={'domain': domain},
                timeout=30
            )
            
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                
                # The enrich endpoint returns data in 'organization' key (singular)
                if data.get('organization'):
                    org = data['organization']
                    logger.info(f"Found Apollo data for {domain}: {org.get('name')}")
                    return org
                else:
                    logger.warning(f"No Apollo data found for domain: {domain}")
                    return None
            elif response.status_code == 401:
                logger.error("Apollo API authentication failed. Check API key.")
                return None
            elif response.status_code == 429:
                logger.warning("Apollo API rate limit hit. Waiting...")
                time.sleep(60)  # Wait a minute
                return None
            else:
                logger.error(f"Apollo API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching Apollo data for {domain}: {str(e)}")
            return None
    
    def save_apollo_data(self, company_id: int, domain: str, org_data: Dict) -> bool:
        """
        Save Apollo organization data to companies table
        
        Args:
            company_id: Company ID in database
            domain: Company domain
            org_data: Apollo organization data
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            # Extract press room URL if available
            press_room_url = None
            website = org_data.get('website_url', '')
            if website:
                # Common press room patterns
                press_room_url = f"{website.rstrip('/')}/newsroom"
            
            # Update company with Apollo data - store FULL apollo_data as JSONB
            # Also extract ticker to dedicated column for easier access
            cursor.execute("""
                UPDATE companies SET
                    name = %s,
                    apollo_data = %s,
                    ticker = %s,
                    status = 'ready',
                    updated_at = NOW()
                WHERE id = %s
            """, (
                org_data.get('name', domain),
                json.dumps(org_data),  # Store complete Apollo response
                org_data.get('ticker'),  # Extract ticker to dedicated column
                company_id
            ))
            
            # Log key Apollo fields for reference
            logger.info(f"Apollo data for {domain}: ticker={org_data.get('ticker')}, "
                       f"employees={org_data.get('estimated_num_employees')}, "
                       f"industry={org_data.get('industry')}, founded={org_data.get('founded_year')}")
            
            self.conn.commit()
            logger.info(f"✅ Saved Apollo data for {domain} (ID: {company_id})")
            return True
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error saving Apollo data for company ID {company_id}: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def mark_no_apollo_data(self, company_id: int, domain: str) -> bool:
        """
        Mark company as having no Apollo data available
        
        Args:
            company_id: Company ID in database
            domain: Company domain
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            # Set name to domain if no Apollo data, mark as ready
            cursor.execute("""
                UPDATE companies 
                SET name = %s,
                    status = 'ready',
                    updated_at = NOW()
                WHERE id = %s
            """, (domain, company_id))
            
            self.conn.commit()
            logger.info(f"✅ Marked {domain} as ready (no Apollo data)")
            return True
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error updating company ID {company_id}: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def process_new_domains(self, limit: int = 10) -> Dict:
        """
        Main processing function - fetch new domains and enrich with Apollo data
        
        Args:
            limit: Maximum number of domains to process
            
        Returns:
            Processing statistics
        """
        stats = {
            'processed': 0,
            'apollo_found': 0,
            'apollo_not_found': 0,
            'errors': 0
        }
        
        # Get new domains
        domains = self.get_new_domains(limit)
        
        if not domains:
            logger.info("No new domains to process")
            return stats
        
        logger.info(f"Processing {len(domains)} domains...")
        
        # Process each domain
        for company_id, domain in domains:
            try:
                # Fetch Apollo data
                org_data = self.fetch_apollo_organization(domain)
                
                if org_data:
                    # Save Apollo data
                    if self.save_apollo_data(company_id, domain, org_data):
                        stats['apollo_found'] += 1
                    else:
                        stats['errors'] += 1
                else:
                    # No Apollo data found
                    if self.mark_no_apollo_data(company_id, domain):
                        stats['apollo_not_found'] += 1
                    else:
                        stats['errors'] += 1
                
                stats['processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing domain {domain}: {str(e)}")
                stats['errors'] += 1
        
        # Log summary
        logger.info(f"Apollo enrichment complete: {stats['processed']} processed, "
                   f"{stats['apollo_found']} found, {stats['apollo_not_found']} not found, "
                   f"{stats['errors']} errors")
        
        return stats
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main execution for standalone running"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Apollo Enrichment Service')
    parser.add_argument('--limit', type=int, default=10,
                        help='Number of domains to process (default: 10)')
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously')
    parser.add_argument('--interval', type=int, default=300,
                        help='Seconds between runs in continuous mode (default: 300)')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("SMARTREACH BIZINTEL - Apollo Enrichment Service")
    print("="*60)
    
    try:
        service = ApolloEnrichmentService()
        
        if args.continuous:
            logger.info(f"Starting continuous mode (interval: {args.interval}s)")
            while True:
                try:
                    stats = service.process_new_domains(args.limit)
                    
                    if stats['processed'] == 0:
                        logger.info(f"No new domains. Waiting {args.interval} seconds...")
                    else:
                        logger.info(f"Batch complete. Waiting {args.interval} seconds...")
                    
                    time.sleep(args.interval)
                    
                except KeyboardInterrupt:
                    logger.info("Stopping continuous mode (user interrupt)")
                    break
                except Exception as e:
                    logger.error(f"Error in continuous mode: {e}")
                    time.sleep(args.interval)
        else:
            # Single run
            stats = service.process_new_domains(args.limit)
            
            print("\n" + "="*60)
            print("ENRICHMENT SUMMARY")
            print("="*60)
            print(f"Processed: {stats['processed']} domains")
            print(f"Apollo Found: {stats['apollo_found']}")
            print(f"Apollo Not Found: {stats['apollo_not_found']}")
            print(f"Errors: {stats['errors']}")
            print("="*60 + "\n")
        
        service.close()
        
    except Exception as e:
        logger.error(f"Service error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())