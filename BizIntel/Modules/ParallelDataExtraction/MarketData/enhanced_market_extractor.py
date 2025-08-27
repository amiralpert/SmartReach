"""
Enhanced Market Data Extractor for SmartReach BizIntel
Extracts comprehensive market data including extended hours, indices, and corporate actions
Week 1 Implementation: Yahoo Finance data with extended capabilities
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import pytz

import yfinance as yf
import pandas as pd
import numpy as np

try:
    from ..base_extractor import BaseExtractor
except ImportError:
    # For standalone testing
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from base_extractor import BaseExtractor


class EnhancedMarketExtractor(BaseExtractor):
    """Enhanced market data extractor with extended hours and indices"""
    
    # Extractor configuration
    extractor_name = "enhanced_market"
    required_fields = []
    rate_limit = "2000/hour"
    needs_auth = False
    
    # Market indices to track
    BIOTECH_INDICES = ['XBI', 'IBB', 'ARKG']  # Biotech-specific
    BROAD_INDICES = ['SPY', 'QQQ', 'IWM']     # Broader market
    
    def __init__(self, db_config: Dict = None):
        """Initialize enhanced market data extractor"""
        super().__init__(db_config)
        
        # Configuration
        self.lookback_days_initial = 730
        self.lookback_days_incremental = 7
        
        # Market hours (EST/EDT)
        self.market_timezone = pytz.timezone('US/Eastern')
        self.market_open = (9, 30)   # 9:30 AM
        self.market_close = (16, 0)  # 4:00 PM
        self.premarket_open = (4, 0)  # 4:00 AM
        self.postmarket_close = (20, 0)  # 8:00 PM
        
        # Indices to extract
        self.indices_to_track = self.BIOTECH_INDICES + self.BROAD_INDICES
        
        self.logger.info(f"Enhanced Market Extractor initialized with indices: {self.indices_to_track}")
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract enhanced market data for a company
        
        Args:
            company_data: Full company data from database
            
        Returns:
            Dict with extraction results
        """
        domain = company_data['domain']
        ticker = company_data.get('ticker')
        
        if not ticker:
            return {
                'status': 'skipped',
                'count': 0,
                'message': f'No ticker found for {domain}'
            }
        
        self.logger.info(f"Starting enhanced extraction for {ticker} ({domain})")
        
        try:
            total_extracted = 0
            
            # 1. Extract company stock data with extended hours
            stock_count = self._extract_stock_data(domain, ticker)
            total_extracted += stock_count
            self.logger.info(f"Extracted {stock_count} stock data points for {ticker}")
            
            # 2. Extract market indices for relative performance
            indices_count = self._extract_indices_data()
            total_extracted += indices_count
            self.logger.info(f"Extracted {indices_count} index data points")
            
            # 3. Extract corporate actions
            actions_count = self._extract_corporate_actions(domain, ticker)
            total_extracted += actions_count
            self.logger.info(f"Extracted {actions_count} corporate actions for {ticker}")
            
            # 4. Calculate peer correlations (if we have enough data)
            self._calculate_peer_correlations(ticker)
            
            return {
                'status': 'success',
                'count': total_extracted,
                'message': f'Extracted {total_extracted} enhanced market data points',
                'data': {
                    'ticker': ticker,
                    'stock_data': stock_count,
                    'indices_data': indices_count,
                    'corporate_actions': actions_count
                }
            }
            
        except Exception as e:
            self.logger.error(f"Enhanced extraction failed for {ticker}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _extract_stock_data(self, domain: str, ticker: str) -> int:
        """Extract stock data with extended hours"""
        try:
            stock = yf.Ticker(ticker)
            
            # Determine lookback period
            last_data_time = self._get_last_data_time(domain)
            if last_data_time:
                # Incremental update - ensure timezone aware comparison
                if last_data_time.tzinfo is None:
                    last_data_time = pytz.UTC.localize(last_data_time)
                start_date = last_data_time - timedelta(days=1)
                self.logger.info(f"Incremental update for {ticker} from {start_date}")
            else:
                # Initial extraction
                start_date = datetime.now(pytz.UTC) - timedelta(days=self.lookback_days_initial)
                self.logger.info(f"Initial extraction for {ticker} from {start_date}")
            
            end_date = datetime.now(pytz.UTC)
            
            saved_count = 0
            
            # Get daily data first (always available)
            df_daily = stock.history(
                start=start_date,
                end=end_date,
                interval='1d',
                prepost=True,  # Include pre and post market
                actions=True   # Include dividends and splits
            )
            
            if not df_daily.empty:
                saved_count += self._save_enhanced_market_data(
                    domain, ticker, df_daily, 86400, 'regular'
                )
            
            # Get intraday data with extended hours (last 60 days max for 5m data)
            intraday_start = max(start_date, datetime.now(pytz.UTC) - timedelta(days=60))
            
            try:
                df_5min = stock.history(
                    start=intraday_start,
                    end=end_date,
                    interval='5m',
                    prepost=True  # KEY: Include pre and post market data
                )
                
                if not df_5min.empty:
                    # Tag each row with market session
                    df_5min['market_session'] = df_5min.index.map(self._determine_market_session)
                    saved_count += self._save_enhanced_market_data(
                        domain, ticker, df_5min, 300, None
                    )
                    
            except Exception as e:
                self.logger.warning(f"Could not get 5-minute data for {ticker}: {e}")
            
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to extract stock data for {ticker}: {e}")
            return 0
    
    def _extract_indices_data(self) -> int:
        """Extract market indices data for relative performance analysis"""
        saved_count = 0
        
        for index_symbol in self.indices_to_track:
            try:
                self.logger.info(f"Extracting index data for {index_symbol}")
                
                index = yf.Ticker(index_symbol)
                
                # Get the index name
                index_name = self._get_index_name(index_symbol)
                
                # Get last 30 days of data (indices don't need as much history)
                df = index.history(
                    period='1mo',
                    interval='1d',
                    prepost=False  # Indices don't have extended hours
                )
                
                if not df.empty:
                    saved_count += self._save_index_data(index_symbol, index_name, df, 86400)
                
                # Also get recent 5-minute data for indices
                df_5min = index.history(
                    period='5d',
                    interval='5m'
                )
                
                if not df_5min.empty:
                    saved_count += self._save_index_data(index_symbol, index_name, df_5min, 300)
                    
            except Exception as e:
                self.logger.error(f"Failed to extract index {index_symbol}: {e}")
                continue
        
        return saved_count
    
    def _extract_corporate_actions(self, domain: str, ticker: str) -> int:
        """Extract corporate actions (splits, dividends, etc.)"""
        try:
            stock = yf.Ticker(ticker)
            saved_count = 0
            
            # Get dividends
            dividends = stock.dividends
            if not dividends.empty:
                saved_count += self._save_corporate_actions(
                    domain, ticker, dividends, 'dividend'
                )
            
            # Get stock splits
            splits = stock.splits
            if not splits.empty:
                saved_count += self._save_corporate_actions(
                    domain, ticker, splits, 'split'
                )
            
            # Get upcoming events from calendar
            try:
                calendar = stock.calendar
                if calendar is not None and not calendar.empty:
                    saved_count += self._save_calendar_events(domain, ticker, calendar)
            except:
                pass  # Calendar might not be available
            
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to extract corporate actions for {ticker}: {e}")
            return 0
    
    def _determine_market_session(self, timestamp) -> str:
        """Determine if timestamp is in pre, regular, or post market"""
        # Convert to Eastern time
        try:
            if hasattr(timestamp, 'tzinfo'):
                if timestamp.tzinfo is None:
                    # Assume UTC if no timezone
                    timestamp = pytz.UTC.localize(timestamp)
                timestamp = timestamp.astimezone(self.market_timezone)
            else:
                # If it's a pandas Timestamp, handle differently
                if timestamp.tz is None:
                    timestamp = timestamp.tz_localize('UTC')
                timestamp = timestamp.tz_convert(self.market_timezone)
        except Exception:
            # Fallback - treat as Eastern time
            pass
        
        hour = timestamp.hour
        minute = timestamp.minute
        time_minutes = hour * 60 + minute
        
        # Define session boundaries in minutes from midnight
        premarket_start = self.premarket_open[0] * 60 + self.premarket_open[1]  # 4:00 AM = 240
        market_open = self.market_open[0] * 60 + self.market_open[1]  # 9:30 AM = 570
        market_close = self.market_close[0] * 60 + self.market_close[1]  # 4:00 PM = 960
        postmarket_close = self.postmarket_close[0] * 60 + self.postmarket_close[1]  # 8:00 PM = 1200
        
        if time_minutes < premarket_start or time_minutes >= postmarket_close:
            return 'closed'
        elif time_minutes < market_open:
            return 'pre'
        elif time_minutes < market_close:
            return 'regular'
        else:
            return 'post'
    
    def _save_enhanced_market_data(self, domain: str, ticker: str, 
                                  df: pd.DataFrame, interval_seconds: int,
                                  default_session: Optional[str]) -> int:
        """Save enhanced market data with session information"""
        if df.empty:
            return 0
        
        conn = None
        cursor = None
        saved_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for timestamp, row in df.iterrows():
                # Skip if essential values are NaN
                if pd.isna(row.get('Close')) or pd.isna(row.get('Volume')):
                    continue
                
                # Determine market session
                if 'market_session' in row:
                    session = row['market_session']
                elif default_session:
                    session = default_session
                else:
                    session = self._determine_market_session(timestamp)
                
                # Skip closed market hours
                if session == 'closed':
                    continue
                
                # Prepare timestamp
                time_utc = timestamp.tz_localize('UTC') if timestamp.tz is None else timestamp.tz_convert('UTC')
                
                # Calculate spread if we have bid/ask (placeholder for now)
                spread = None
                
                cursor.execute("""
                    INSERT INTO market_data 
                    (time, company_domain, ticker, open, high, low, close, volume,
                     adj_open, adj_high, adj_low, adj_close, interval_seconds, 
                     market_session, spread, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_domain, time, interval_seconds) 
                    DO UPDATE SET
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        market_session = EXCLUDED.market_session
                """, (
                    time_utc,
                    domain,
                    ticker,
                    float(row['Open']) if not pd.isna(row.get('Open')) else None,
                    float(row['High']) if not pd.isna(row.get('High')) else None,
                    float(row['Low']) if not pd.isna(row.get('Low')) else None,
                    float(row['Close']),
                    int(row['Volume']),
                    float(row['Open']) if not pd.isna(row.get('Open')) else None,
                    float(row['High']) if not pd.isna(row.get('High')) else None,
                    float(row['Low']) if not pd.isna(row.get('Low')) else None,
                    float(row['Close']),
                    interval_seconds,
                    session,
                    spread,
                    'yahoo'
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
            
            conn.commit()
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to save enhanced market data: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _save_index_data(self, symbol: str, name: str, df: pd.DataFrame, interval_seconds: int) -> int:
        """Save market index data"""
        if df.empty:
            return 0
        
        conn = None
        cursor = None
        saved_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for timestamp, row in df.iterrows():
                if pd.isna(row.get('Close')):
                    continue
                
                time_utc = timestamp.tz_localize('UTC') if timestamp.tz is None else timestamp.tz_convert('UTC')
                
                # Calculate daily return
                daily_return = None
                if interval_seconds == 86400 and 'Close' in row:
                    # Will be calculated in SQL using LAG function
                    pass
                
                cursor.execute("""
                    INSERT INTO market_indices 
                    (time, symbol, name, open, high, low, close, volume,
                     interval_seconds, market_session, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, time, interval_seconds) 
                    DO UPDATE SET
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """, (
                    time_utc,
                    symbol,
                    name,
                    float(row['Open']) if not pd.isna(row.get('Open')) else None,
                    float(row['High']) if not pd.isna(row.get('High')) else None,
                    float(row['Low']) if not pd.isna(row.get('Low')) else None,
                    float(row['Close']),
                    int(row['Volume']) if not pd.isna(row.get('Volume')) else 0,
                    interval_seconds,
                    'regular',  # Indices trade only in regular hours
                    'yahoo'
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
            
            conn.commit()
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to save index data: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _save_corporate_actions(self, domain: str, ticker: str, 
                               actions: pd.Series, action_type: str) -> int:
        """Save corporate actions to database"""
        if actions.empty:
            return 0
        
        conn = None
        cursor = None
        saved_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for date, value in actions.items():
                # Prepare details JSON based on action type
                if action_type == 'dividend':
                    details = {'amount': float(value)}
                elif action_type == 'split':
                    details = {'split_factor': float(value)}
                else:
                    details = {'value': float(value)}
                
                cursor.execute("""
                    INSERT INTO corporate_actions 
                    (company_domain, ticker, action_date, action_type, details, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_domain, action_date, action_type) 
                    DO UPDATE SET
                        details = EXCLUDED.details
                """, (
                    domain,
                    ticker,
                    date.date() if hasattr(date, 'date') else date,
                    action_type,
                    json.dumps(details),
                    'yahoo'
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
            
            conn.commit()
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to save corporate actions: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _save_calendar_events(self, domain: str, ticker: str, calendar: pd.DataFrame) -> int:
        """Save upcoming calendar events (earnings, etc.)"""
        saved_count = 0
        
        try:
            if 'Earnings Date' in calendar.index:
                earnings_date = calendar.loc['Earnings Date']
                if pd.notna(earnings_date):
                    # Save as corporate action
                    conn = self.get_db_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO corporate_actions 
                        (company_domain, ticker, action_date, action_type, 
                         details, announcement_date, data_source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (company_domain, action_date, action_type) 
                        DO NOTHING
                    """, (
                        domain,
                        ticker,
                        earnings_date,
                        'earnings',
                        json.dumps({'status': 'upcoming'}),
                        datetime.now().date(),
                        'yahoo'
                    ))
                    
                    if cursor.rowcount > 0:
                        saved_count += 1
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
        except Exception as e:
            self.logger.warning(f"Could not save calendar events: {e}")
        
        return saved_count
    
    def _calculate_peer_correlations(self, ticker: str):
        """Calculate correlations with peer stocks"""
        # This will be implemented in Week 2
        # For now, just log that we'll calculate correlations
        self.logger.info(f"Peer correlation calculation for {ticker} scheduled for Week 2")
    
    def _get_index_name(self, symbol: str) -> str:
        """Get friendly name for index symbol"""
        index_names = {
            'XBI': 'SPDR S&P Biotech ETF',
            'IBB': 'iShares Biotechnology ETF',
            'ARKG': 'ARK Genomic Revolution ETF',
            'SPY': 'SPDR S&P 500 ETF',
            'QQQ': 'Invesco QQQ Trust',
            'IWM': 'iShares Russell 2000 ETF'
        }
        return index_names.get(symbol, symbol)
    
    def _get_last_data_time(self, domain: str) -> Optional[datetime]:
        """Get the timestamp of the last data point for a company"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT MAX(time) 
                FROM market_data 
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


# For testing and standalone use
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Fix imports for standalone execution
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from Modules.ParallelDataExtraction.base_extractor import BaseExtractor
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Test with a specific company or default
    if len(sys.argv) > 1:
        test_ticker = sys.argv[1]
        test_domain = f"{test_ticker.lower()}.com"
    else:
        test_ticker = "GH"
        test_domain = "guardanthealth.com"
    
    # Create test company data
    company_data = {
        'domain': test_domain,
        'ticker': test_ticker,
        'name': f'Test extraction for {test_ticker}'
    }
    
    # Create extractor and run
    extractor = EnhancedMarketExtractor()
    result = extractor.extract(company_data)
    
    print(f"Enhanced Market Extraction Result: {json.dumps(result, indent=2)}")