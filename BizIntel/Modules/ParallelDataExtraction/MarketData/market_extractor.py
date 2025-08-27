"""
Market Data Extractor for SmartReach BizIntel
Extracts stock price and volume data using Yahoo Finance API
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import pytz

import yfinance as yf
import pandas as pd
from ..base_extractor import BaseExtractor


class MarketExtractor(BaseExtractor):
    """Extract market data using Yahoo Finance API"""
    
    # Extractor configuration
    extractor_name = "market"
    required_fields = []  # ticker will be checked separately
    rate_limit = "2000/hour"  # Yahoo Finance unofficial limit
    needs_auth = False
    
    def __init__(self, db_config: Dict = None):
        """Initialize market data extractor"""
        super().__init__(db_config)
        
        # Configuration
        self.lookback_days_initial = 730  # 2 years of historical data
        self.lookback_days_incremental = 7  # 1 week for updates
        self.min_market_cap = 100_000_000  # $100M minimum for data quality
        
        # Market hours (EST/EDT)
        self.market_timezone = pytz.timezone('US/Eastern')
        self.market_open_time = (9, 30)  # 9:30 AM
        self.market_close_time = (16, 0)  # 4:00 PM
        
        # Cache for market calendar
        self._trading_days_cache = {}
    
    def can_extract(self, company_data: Dict) -> bool:
        """
        Check if market data extraction is possible for this company
        
        Args:
            company_data: Company information from database
            
        Returns:
            bool: True if we have a ticker symbol
        """
        # Check for ticker symbol
        ticker = company_data.get('ticker')
        
        if not ticker:
            self.logger.info(f"No ticker found for {company_data.get('domain')}")
            return False
        
        # Check if ticker is valid format (basic validation)
        if not ticker.replace('-', '').replace('.', '').isalnum():
            self.logger.warning(f"Invalid ticker format: {ticker}")
            return False
        
        return True
    
    def is_market_open(self) -> tuple[bool, str]:
        """
        Check if the US stock market is currently open for trading
        
        Returns:
            tuple: (is_open: bool, reason: str)
        """
        # Get current time in Eastern timezone
        now_et = datetime.now(self.market_timezone)
        weekday = now_et.weekday()
        
        # Check if weekend (Saturday=5, Sunday=6)
        if weekday >= 5:
            return False, "Market closed - weekend"
        
        # Check if within market hours
        market_open = now_et.replace(
            hour=self.market_open_time[0], 
            minute=self.market_open_time[1], 
            second=0, 
            microsecond=0
        )
        market_close = now_et.replace(
            hour=self.market_close_time[0], 
            minute=self.market_close_time[1], 
            second=0, 
            microsecond=0
        )
        
        if now_et < market_open:
            return False, "Market closed - pre-market hours"
        elif now_et > market_close:
            return False, "Market closed - after hours"
        else:
            return True, "Market open"
    
    def should_extract(self, company_data: Dict, force: bool = False) -> tuple[bool, str]:
        """
        Determine if extraction should proceed based on market hours and data freshness
        
        Args:
            company_data: Company information from database
            force: Force extraction regardless of market hours
            
        Returns:
            tuple: (should_extract: bool, reason: str)
        """
        if force:
            return True, "Force extraction requested"
        
        # Check if this is initial extraction (always proceed)
        domain = company_data['domain']
        last_data_time = self._get_last_data_time(domain)
        
        if last_data_time is None:
            # Initial extraction - always get historical data
            return True, "Initial historical data extraction"
        
        # For incremental updates, check market hours
        is_open, market_status = self.is_market_open()
        
        if not is_open:
            # Check how stale the data is
            now = datetime.now(pytz.UTC)
            if last_data_time:
                last_data_time_utc = last_data_time.replace(tzinfo=pytz.UTC) if last_data_time.tzinfo is None else last_data_time
                hours_since_last = (now - last_data_time_utc).total_seconds() / 3600
                
                # If data is very stale (>48 hours), extract anyway
                if hours_since_last > 48:
                    return True, f"Data is {hours_since_last:.1f} hours old, extracting despite market closed"
            
            return False, market_status
        
        return True, "Market open - proceeding with extraction"
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract market data for a company
        
        Args:
            company_data: Full company data from database
            
        Returns:
            Dict with extraction results
        """
        domain = company_data['domain']
        company_name = company_data.get('name', domain)
        ticker = company_data.get('ticker')
        
        if not ticker:
            return {
                'status': 'skipped',
                'count': 0,
                'message': 'No ticker symbol available'
            }
        
        self.logger.info(f"Extracting market data for {company_name} ({ticker})")
        
        # Check if we should extract based on market hours
        should_extract, reason = self.should_extract(company_data)
        
        if not should_extract:
            self.logger.info(f"Skipping {company_name}: {reason}")
            return {
                'status': 'skipped',
                'count': 0,
                'message': reason,
                'data': {
                    'ticker': ticker,
                    'market_status': reason
                }
            }
        
        try:
            # Check if we need historical or incremental data
            last_data_time = self._get_last_data_time(domain)
            
            if last_data_time is None:
                # Initial extraction - get historical data
                data_points = self._extract_historical_data(domain, ticker)
            else:
                # Incremental extraction - get recent data
                data_points = self._extract_incremental_data(domain, ticker, last_data_time)
            
            if data_points > 0:
                # Clear any existing alerts for this company
                self._clear_alerts(domain)
                
                self.logger.info(f"Extracted {data_points} market data points for {company_name}")
                
                return {
                    'status': 'success',
                    'count': data_points,
                    'message': f'Extracted {data_points} market data points',
                    'data': {
                        'ticker': ticker,
                        'data_points': data_points,
                        'extraction_type': 'historical' if last_data_time is None else 'incremental'
                    }
                }
            else:
                # No data returned - create alert
                self._handle_no_data(domain, ticker, last_data_time)
                
                return {
                    'status': 'failed',
                    'count': 0,
                    'message': f'No market data available for ticker {ticker}'
                }
                
        except Exception as e:
            self.logger.error(f"Market data extraction failed for {domain}: {e}")
            self._create_alert(domain, 'api_error', str(e), ticker)
            
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _extract_historical_data(self, domain: str, ticker: str) -> int:
        """Extract 2 years of historical data"""
        try:
            # Get 2 years of daily data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_days_initial)
            
            # Download data
            stock = yf.Ticker(ticker)
            df_daily = stock.history(start=start_date, end=end_date, interval='1d')
            
            if df_daily.empty:
                return 0
            
            # Process daily data
            daily_count = self._save_market_data(domain, ticker, df_daily, 86400)  # 86400 = daily
            
            # Get recent 30 days of 5-minute data if available
            recent_start = end_date - timedelta(days=30)
            try:
                df_5min = stock.history(start=recent_start, end=end_date, interval='5m')
                if not df_5min.empty:
                    minute_count = self._save_market_data(domain, ticker, df_5min, 300)  # 300 = 5 minutes
                    return daily_count + minute_count
            except Exception as e:
                self.logger.warning(f"Could not get 5-minute data for {ticker}: {e}")
            
            return daily_count
            
        except Exception as e:
            self.logger.error(f"Failed to extract historical data for {ticker}: {e}")
            return 0
    
    def _extract_incremental_data(self, domain: str, ticker: str, last_data_time: datetime) -> int:
        """Extract recent data since last extraction"""
        try:
            # Get data since last extraction
            start_date = last_data_time - timedelta(hours=1)  # Small overlap to avoid gaps
            end_date = datetime.now()
            
            # Only get 5-minute data for incremental updates
            stock = yf.Ticker(ticker)
            
            # Try 5-minute data first
            try:
                df = stock.history(start=start_date, end=end_date, interval='5m')
                if not df.empty:
                    return self._save_market_data(domain, ticker, df, 300)
            except Exception as e:
                self.logger.warning(f"Could not get 5-minute data for {ticker}, trying daily: {e}")
            
            # Fallback to daily data
            df = stock.history(start=start_date, end=end_date, interval='1d')
            if not df.empty:
                return self._save_market_data(domain, ticker, df, 86400)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to extract incremental data for {ticker}: {e}")
            return 0
    
    def _save_market_data(self, domain: str, ticker: str, df: pd.DataFrame, interval_seconds: int) -> int:
        """Save market data to database"""
        if df.empty:
            return 0
        
        conn = None
        cursor = None
        saved_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for timestamp, row in df.iterrows():
                # Skip if any essential values are NaN
                if pd.isna(row['Close']) or pd.isna(row['Volume']):
                    continue
                
                # Prepare data
                time_utc = timestamp.tz_localize('UTC') if timestamp.tz is None else timestamp.tz_convert('UTC')
                
                cursor.execute("""
                    INSERT INTO market_data 
                    (time, company_domain, ticker, open, high, low, close, volume,
                     adj_open, adj_high, adj_low, adj_close, interval_seconds, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_domain, time, interval_seconds) DO NOTHING
                """, (
                    time_utc,
                    domain,
                    ticker,
                    float(row['Open']) if not pd.isna(row['Open']) else None,
                    float(row['High']) if not pd.isna(row['High']) else None,
                    float(row['Low']) if not pd.isna(row['Low']) else None,
                    float(row['Close']),
                    int(row['Volume']),
                    # Adjusted prices (yfinance doesn't provide these separately for 5min data)
                    float(row['Open']) if not pd.isna(row['Open']) else None,
                    float(row['High']) if not pd.isna(row['High']) else None,
                    float(row['Low']) if not pd.isna(row['Low']) else None,
                    float(row['Close']),
                    interval_seconds,
                    'yahoo'
                ))
                saved_count += 1
            
            conn.commit()
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to save market data: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _get_last_data_time(self, domain: str) -> Optional[datetime]:
        """Get the timestamp of the most recent market data for this company"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT MAX(time) FROM market_data 
                WHERE company_domain = %s
            """, (domain,))
            
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
            
        except Exception as e:
            self.logger.error(f"Failed to get last data time: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _handle_no_data(self, domain: str, ticker: str, last_data_time: Optional[datetime]):
        """Handle case where no data was returned"""
        if last_data_time:
            # We used to get data, now we don't - ticker might be invalid
            self._create_alert(
                domain=domain,
                alert_type='ticker_invalid',
                message=f'Ticker {ticker} no longer returning data (last success: {last_data_time})',
                ticker=ticker,
                severity='error'
            )
        else:
            # Never got data - might be wrong ticker
            self._create_alert(
                domain=domain,
                alert_type='ticker_never_worked',
                message=f'Ticker {ticker} has never returned market data',
                ticker=ticker,
                severity='warning'
            )
    
    def _create_alert(self, domain: str, alert_type: str, message: str, ticker: str = None, severity: str = 'warning'):
        """Create or update a market alert"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get last successful extraction time
            cursor.execute("""
                SELECT MAX(extracted_at) FROM market_data 
                WHERE company_domain = %s
            """, (domain,))
            last_success = cursor.fetchone()[0]
            
            # Determine suggested action based on alert type
            suggested_actions = {
                'ticker_invalid': f'Check if {ticker} was delisted, merged, or changed. Search Yahoo Finance for current symbol.',
                'ticker_never_worked': f'Verify ticker symbol. Consider Apollo re-enrichment for {domain}.',
                'api_error': 'Check Yahoo Finance API status. May be temporary issue.',
                'no_data_returned': f'Verify {ticker} is a valid, publicly traded symbol.'
            }
            
            suggested_action = suggested_actions.get(alert_type, 'Manual investigation required.')
            
            cursor.execute("""
                INSERT INTO market_alerts 
                (company_domain, alert_type, alert_severity, data_source, 
                 failed_identifier, last_successful_extraction, error_message, suggested_action)
                VALUES (%s, %s, %s, 'market', %s, %s, %s, %s)
                ON CONFLICT (company_domain, alert_type, failed_identifier, alert_status)
                DO UPDATE SET
                    failure_count = market_alerts.failure_count + 1,
                    error_message = EXCLUDED.error_message,
                    created_at = CASE 
                        WHEN market_alerts.failure_count = 1 THEN market_alerts.created_at
                        ELSE CURRENT_TIMESTAMP
                    END
            """, (domain, alert_type, severity, ticker, last_success, message, suggested_action))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to create alert: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _clear_alerts(self, domain: str):
        """Clear active alerts for a company after successful extraction"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE market_alerts 
                SET alert_status = 'resolved',
                    resolved_at = CURRENT_TIMESTAMP,
                    resolution_notes = 'Data extraction successful'
                WHERE company_domain = %s 
                  AND alert_status = 'active'
                  AND data_source = 'market'
            """, (domain,))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to clear alerts: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# For testing and standalone use
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    # Get domain from command line or use default
    domain = sys.argv[1] if len(sys.argv) > 1 else "grail.com"
    
    # Create extractor and run
    extractor = MarketExtractor()
    result = extractor.run(domain)
    
    print(f"Market Data Extraction Result: {json.dumps(result, indent=2, default=str)}")