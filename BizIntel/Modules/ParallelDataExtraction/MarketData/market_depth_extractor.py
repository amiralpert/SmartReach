"""
Market Depth Extractor using Alpaca Markets API
Provides real-time bid/ask spreads, VWAP, and liquidity metrics
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import pytz

import pandas as pd
import numpy as np
from alpaca_client import AlpacaClient

try:
    from ..base_extractor import BaseExtractor
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from base_extractor import BaseExtractor


class MarketDepthExtractor(BaseExtractor):
    """Extract real-time market depth and microstructure data using Alpaca"""
    
    # Extractor configuration
    extractor_name = "market_depth"
    required_fields = []
    rate_limit = "200/minute"  # Alpaca rate limit
    needs_auth = True
    
    def __init__(self, db_config: Dict = None):
        """Initialize market depth extractor"""
        super().__init__(db_config)
        
        # Initialize Alpaca client
        self.alpaca = AlpacaClient(paper=True)  # Use paper trading endpoint
        
        # Configuration
        self.lookback_minutes = 60  # Get last hour of bars for VWAP
        self.bar_timeframe = '5Min'  # 5-minute bars
        
        self.logger.info("Market Depth Extractor initialized with Alpaca API")
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract market depth data for a company
        
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
        
        # Check if market is open
        if not self.alpaca.is_market_open():
            self.logger.info(f"Market closed - getting latest available data for {ticker}")
        
        self.logger.info(f"Extracting market depth for {ticker} ({domain})")
        
        try:
            extracted_count = 0
            
            # 1. Get latest quote (bid/ask)
            quote = self.alpaca.get_latest_quote(ticker)
            if quote:
                saved = self._save_market_quote(domain, ticker, quote)
                extracted_count += saved
                self.logger.info(f"Saved quote data for {ticker}: Spread ${quote['spread']:.4f}")
            
            # 2. Get latest trade
            trade = self.alpaca.get_latest_trade(ticker)
            if trade:
                self.logger.info(f"Latest trade for {ticker}: ${trade['price']:.2f} x {trade['size']}")
            
            # 3. Get historical bars with VWAP
            end_time = datetime.now(pytz.UTC)
            start_time = end_time - timedelta(minutes=self.lookback_minutes)
            
            bars_df = self.alpaca.get_bars(
                ticker, 
                self.bar_timeframe,
                start=start_time,
                end=end_time
            )
            
            if not bars_df.empty:
                saved = self._save_market_bars(domain, ticker, bars_df)
                extracted_count += saved
                self.logger.info(f"Saved {saved} bars with VWAP for {ticker}")
            
            # 4. Get complete snapshot
            snapshot = self.alpaca.get_snapshot(ticker)
            if snapshot:
                # Calculate additional metrics
                metrics = self._calculate_market_metrics(snapshot)
                self.logger.info(f"Market metrics for {ticker}: {metrics}")
            
            if extracted_count > 0:
                return {
                    'status': 'success',
                    'count': extracted_count,
                    'message': f'Extracted {extracted_count} market depth data points',
                    'data': {
                        'ticker': ticker,
                        'spread': quote['spread'] if quote else None,
                        'spread_quality': self.alpaca._assess_spread_quality(quote) if quote else None,
                        'liquidity_score': self.alpaca._calculate_liquidity_score(quote) if quote else None,
                        'vwap_bars': len(bars_df) if not bars_df.empty else 0
                    }
                }
            else:
                return {
                    'status': 'failed',
                    'count': 0,
                    'message': f'No market depth data available for {ticker}'
                }
            
        except Exception as e:
            self.logger.error(f"Market depth extraction failed for {ticker}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _save_market_quote(self, domain: str, ticker: str, quote: Dict) -> int:
        """Save bid/ask quote data to database"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Save enhanced market data with bid/ask
            cursor.execute("""
                UPDATE market_data 
                SET 
                    bid = %s,
                    ask = %s,
                    spread = %s,
                    bid_size = %s,
                    ask_size = %s
                WHERE company_domain = %s 
                  AND ticker = %s
                  AND time = (
                      SELECT MAX(time) 
                      FROM market_data 
                      WHERE company_domain = %s AND ticker = %s
                  )
            """, (
                quote['bid'],
                quote['ask'],
                quote['spread'],
                quote['bid_size'],
                quote['ask_size'],
                domain,
                ticker,
                domain,
                ticker
            ))
            
            updated = cursor.rowcount
            
            # If no recent record to update, insert new one
            if updated == 0:
                cursor.execute("""
                    INSERT INTO market_data 
                    (time, company_domain, ticker, bid, ask, spread, 
                     bid_size, ask_size, interval_seconds, market_session, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    quote['timestamp'],
                    domain,
                    ticker,
                    quote['bid'],
                    quote['ask'],
                    quote['spread'],
                    quote['bid_size'],
                    quote['ask_size'],
                    0,  # Quote, not a bar
                    'regular',
                    'alpaca'
                ))
                updated = cursor.rowcount
            
            conn.commit()
            return updated
            
        except Exception as e:
            self.logger.error(f"Error saving market quote: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _save_market_bars(self, domain: str, ticker: str, bars_df: pd.DataFrame) -> int:
        """Save bars with VWAP to database"""
        if bars_df.empty:
            return 0
        
        conn = None
        cursor = None
        saved_count = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Determine interval in seconds based on timeframe
            interval_map = {
                '1Min': 60,
                '5Min': 300,
                '15Min': 900,
                '1Hour': 3600,
                '1Day': 86400
            }
            interval_seconds = interval_map.get(self.bar_timeframe, 300)
            
            for timestamp, row in bars_df.iterrows():
                # Skip if essential values are missing
                if pd.isna(row.get('close')) or pd.isna(row.get('volume')):
                    continue
                
                cursor.execute("""
                    INSERT INTO market_data 
                    (time, company_domain, ticker, open, high, low, close, volume,
                     vwap, interval_seconds, market_session, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_domain, time, interval_seconds) 
                    DO UPDATE SET
                        vwap = EXCLUDED.vwap,
                        volume = EXCLUDED.volume,
                        close = EXCLUDED.close
                """, (
                    timestamp,
                    domain,
                    ticker,
                    float(row['open']) if not pd.isna(row.get('open')) else None,
                    float(row['high']) if not pd.isna(row.get('high')) else None,
                    float(row['low']) if not pd.isna(row.get('low')) else None,
                    float(row['close']),
                    int(row['volume']),
                    float(row['vwap']) if not pd.isna(row.get('vwap')) else None,
                    interval_seconds,
                    'regular',  # Alpaca only provides regular hours
                    'alpaca'
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
            
            conn.commit()
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Error saving market bars: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _calculate_market_metrics(self, snapshot: Dict) -> Dict:
        """Calculate additional market microstructure metrics"""
        metrics = {}
        
        if 'latest_quote' in snapshot:
            quote = snapshot['latest_quote']
            # Bid-ask midpoint
            metrics['midpoint'] = (quote['bid'] + quote['ask']) / 2
            
            # Relative spread (spread as % of midpoint)
            if metrics['midpoint'] > 0:
                metrics['relative_spread'] = (quote['spread'] / metrics['midpoint']) * 100
            
            # Depth imbalance (bid size vs ask size)
            total_size = quote['bid_size'] + quote['ask_size']
            if total_size > 0:
                metrics['depth_imbalance'] = (quote['bid_size'] - quote['ask_size']) / total_size
        
        if 'daily_stats' in snapshot:
            stats = snapshot['daily_stats']
            # VWAP deviation
            if stats.get('vwap') and 'latest_trade' in snapshot:
                current_price = snapshot['latest_trade']['price']
                metrics['vwap_deviation'] = ((current_price - stats['vwap']) / stats['vwap']) * 100
            
            # Daily range utilization
            if stats['high'] > stats['low']:
                if 'latest_trade' in snapshot:
                    current_price = snapshot['latest_trade']['price']
                    metrics['range_position'] = (current_price - stats['low']) / (stats['high'] - stats['low'])
        
        return metrics
    
    def extract_batch(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Extract market depth for multiple tickers efficiently
        
        Args:
            tickers: List of stock symbols
            
        Returns:
            Dict mapping tickers to their market depth data
        """
        results = {}
        
        # Get market depth for all tickers
        depth_data = self.alpaca.get_market_depth(tickers)
        
        for ticker, data in depth_data.items():
            if data:
                results[ticker] = {
                    'status': 'success',
                    'bid': data['quote']['bid'] if data.get('quote') else None,
                    'ask': data['quote']['ask'] if data.get('quote') else None,
                    'spread': data['quote']['spread'] if data.get('quote') else None,
                    'liquidity_score': data.get('liquidity_score'),
                    'spread_quality': data.get('spread_quality'),
                    'last_price': data['trade']['price'] if data.get('trade') else None
                }
            else:
                results[ticker] = {
                    'status': 'failed',
                    'message': 'No data available'
                }
        
        return results
    
    def monitor_spreads(self, tickers: List[str], duration_minutes: int = 5,
                        callback=None) -> pd.DataFrame:
        """
        Monitor spread changes over time
        
        Args:
            tickers: List of tickers to monitor
            duration_minutes: How long to monitor
            callback: Optional function to call with each update
            
        Returns:
            DataFrame with spread history
        """
        spread_history = []
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        self.logger.info(f"Monitoring spreads for {tickers} for {duration_minutes} minutes")
        
        while datetime.now() < end_time:
            for ticker in tickers:
                try:
                    quote = self.alpaca.get_latest_quote(ticker)
                    if quote:
                        record = {
                            'timestamp': datetime.now(),
                            'ticker': ticker,
                            'bid': quote['bid'],
                            'ask': quote['ask'],
                            'spread': quote['spread'],
                            'spread_pct': quote['spread_pct'],
                            'bid_size': quote['bid_size'],
                            'ask_size': quote['ask_size']
                        }
                        spread_history.append(record)
                        
                        if callback:
                            callback(record)
                        
                except Exception as e:
                    self.logger.error(f"Error monitoring {ticker}: {e}")
            
            # Wait 5 seconds between checks
            time.sleep(5)
        
        return pd.DataFrame(spread_history)


# For testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Database config
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Test ticker
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "GH"
    
    # Create test company data - use real domain from database
    test_companies = {
        'GH': 'guardanthealth.com',
        'EXAS': 'www.exactsciences.com',
        'AAPL': 'apple.com',
        'MRNA': 'modernatx.com'
    }
    
    company_data = {
        'domain': test_companies.get(test_ticker, f'{test_ticker.lower()}.com'),
        'ticker': test_ticker,
        'name': f'Test extraction for {test_ticker}'
    }
    
    print(f"\n{'='*60}")
    print(f"Testing Market Depth Extractor with {test_ticker}")
    print(f"{'='*60}")
    
    # Create extractor and run
    extractor = MarketDepthExtractor(db_config)
    result = extractor.extract(company_data)
    
    print(f"\nExtraction Result:")
    print(json.dumps(result, indent=2, default=str))
    
    # Test batch extraction
    if result['status'] == 'success':
        print(f"\n\nTesting Batch Extraction:")
        batch_tickers = ['AAPL', 'MSFT', 'GOOGL', 'MRNA']
        batch_results = extractor.extract_batch(batch_tickers)
        
        for ticker, data in batch_results.items():
            if data['status'] == 'success':
                print(f"  {ticker}: Bid ${data['bid']:.2f} / Ask ${data['ask']:.2f} / Spread ${data['spread']:.4f}")
            else:
                print(f"  {ticker}: {data['message']}")
    
    print(f"\n{'='*60}\n")