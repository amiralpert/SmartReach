"""
Alpaca Markets API Client for SmartReach BizIntel
Provides real-time market depth, quotes, and trade data
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import pytz

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
import pandas as pd
import numpy as np


class AlpacaClient:
    """Alpaca Markets API wrapper for market depth and real-time data"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, paper: bool = True):
        """
        Initialize Alpaca client
        
        Args:
            api_key: Alpaca API key (or from env)
            api_secret: Alpaca API secret (or from env)
            paper: Use paper trading endpoint (True) or live (False)
        """
        self.logger = logging.getLogger(__name__)
        
        # Get credentials from env if not provided
        self.api_key = api_key or os.getenv('ALPACA_KEY')
        self.api_secret = api_secret or os.getenv('ALPACA_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Alpaca API credentials not found. Check .env file.")
        
        # Set base URL based on paper/live mode
        if paper:
            base_url = 'https://paper-api.alpaca.markets'
            self.logger.info("Using Alpaca Paper Trading API")
        else:
            base_url = 'https://api.alpaca.markets'
            self.logger.info("Using Alpaca Live Trading API")
        
        # Initialize API client
        self.api = tradeapi.REST(
            self.api_key,
            self.api_secret,
            base_url,
            api_version='v2'
        )
        
        # Rate limiting: 200 requests per minute
        self.rate_limit = 200
        self.rate_window = 60  # seconds
        self.request_times = []
        
        # Market timezone
        self.market_tz = pytz.timezone('US/Eastern')
        
        # Test connection
        try:
            account = self.api.get_account()
            self.logger.info(f"Connected to Alpaca. Account status: {account.status}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Alpaca: {e}")
            raise
    
    def _check_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        now = time.time()
        
        # Remove requests older than rate window
        self.request_times = [t for t in self.request_times if now - t < self.rate_window]
        
        # If at limit, wait
        if len(self.request_times) >= self.rate_limit:
            sleep_time = self.rate_window - (now - self.request_times[0]) + 0.1
            if sleep_time > 0:
                self.logger.debug(f"Rate limit reached. Sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        # Record this request
        self.request_times.append(now)
    
    def get_latest_quote(self, symbol: str) -> Dict:
        """
        Get latest quote (bid/ask) for a symbol
        
        Returns:
            Dict with bid, ask, bid_size, ask_size, spread
        """
        self._check_rate_limit()
        
        try:
            quote = self.api.get_latest_quote(symbol)
            
            if quote:
                spread = float(quote.ask_price) - float(quote.bid_price)
                spread_pct = (spread / float(quote.bid_price)) * 100 if quote.bid_price > 0 else None
                
                return {
                    'symbol': symbol,
                    'bid': float(quote.bid_price),
                    'ask': float(quote.ask_price),
                    'bid_size': int(quote.bid_size),
                    'ask_size': int(quote.ask_size),
                    'spread': spread,
                    'spread_pct': spread_pct,
                    'timestamp': quote.timestamp,
                    'conditions': quote.conditions if hasattr(quote, 'conditions') else None
                }
            return None
            
        except APIError as e:
            self.logger.error(f"API error getting quote for {symbol}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    def get_latest_trade(self, symbol: str) -> Dict:
        """
        Get latest trade for a symbol
        
        Returns:
            Dict with price, size, timestamp, conditions
        """
        self._check_rate_limit()
        
        try:
            trade = self.api.get_latest_trade(symbol)
            
            if trade:
                return {
                    'symbol': symbol,
                    'price': float(trade.price),
                    'size': int(trade.size),
                    'timestamp': trade.timestamp,
                    'conditions': trade.conditions if hasattr(trade, 'conditions') else None,
                    'exchange': trade.exchange if hasattr(trade, 'exchange') else None
                }
            return None
            
        except APIError as e:
            self.logger.error(f"API error getting trade for {symbol}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting trade for {symbol}: {e}")
            return None
    
    def get_bars(self, symbol: str, timeframe: str = '5Min', 
                 start: datetime = None, end: datetime = None,
                 limit: int = 100) -> pd.DataFrame:
        """
        Get historical bars with VWAP
        
        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
            start: Start datetime
            end: End datetime
            limit: Maximum number of bars
            
        Returns:
            DataFrame with OHLCV and VWAP data
        """
        self._check_rate_limit()
        
        try:
            # Set default time range if not provided
            if not end:
                end = datetime.now(pytz.UTC)
            if not start:
                start = end - timedelta(days=1)
            
            # Get bars
            bars = self.api.get_bars(
                symbol,
                timeframe,
                start=start.isoformat(),
                end=end.isoformat(),
                limit=limit
            )
            
            if bars:
                # Convert to DataFrame
                df = pd.DataFrame([{
                    'time': bar.t,
                    'open': float(bar.o),
                    'high': float(bar.h),
                    'low': float(bar.l),
                    'close': float(bar.c),
                    'volume': int(bar.v),
                    'vwap': float(bar.vw) if hasattr(bar, 'vw') else None,
                    'trade_count': int(bar.n) if hasattr(bar, 'n') else None
                } for bar in bars])
                
                if not df.empty:
                    df['time'] = pd.to_datetime(df['time'])
                    df.set_index('time', inplace=True)
                    
                    # Calculate additional metrics
                    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
                    df['money_flow'] = df['typical_price'] * df['volume']
                    
                    return df
            
            return pd.DataFrame()
            
        except APIError as e:
            self.logger.error(f"API error getting bars for {symbol}: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error getting bars for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_snapshot(self, symbol: str) -> Dict:
        """
        Get complete snapshot of a symbol (quote + trade + daily bar)
        
        Returns:
            Dict with latest quote, trade, and daily stats
        """
        self._check_rate_limit()
        
        try:
            snapshot = self.api.get_snapshot(symbol)
            
            if snapshot:
                result = {
                    'symbol': symbol,
                    'updated_at': datetime.now(pytz.UTC)
                }
                
                # Latest trade
                if snapshot.latest_trade:
                    result['latest_trade'] = {
                        'price': float(snapshot.latest_trade.price),
                        'size': int(snapshot.latest_trade.size),
                        'timestamp': snapshot.latest_trade.timestamp
                    }
                
                # Latest quote
                if snapshot.latest_quote:
                    result['latest_quote'] = {
                        'bid': float(snapshot.latest_quote.bid_price),
                        'ask': float(snapshot.latest_quote.ask_price),
                        'bid_size': int(snapshot.latest_quote.bid_size),
                        'ask_size': int(snapshot.latest_quote.ask_size),
                        'spread': float(snapshot.latest_quote.ask_price) - float(snapshot.latest_quote.bid_price)
                    }
                
                # Daily bar
                if snapshot.daily_bar:
                    result['daily_stats'] = {
                        'open': float(snapshot.daily_bar.open),
                        'high': float(snapshot.daily_bar.high),
                        'low': float(snapshot.daily_bar.low),
                        'close': float(snapshot.daily_bar.close),
                        'volume': int(snapshot.daily_bar.volume),
                        'vwap': float(snapshot.daily_bar.vwap) if hasattr(snapshot.daily_bar, 'vwap') else None
                    }
                
                # Previous daily bar for change calculation
                if snapshot.prev_daily_bar:
                    prev_close = float(snapshot.prev_daily_bar.close)
                    curr_price = result.get('latest_trade', {}).get('price', 0)
                    if prev_close > 0 and curr_price > 0:
                        result['change'] = curr_price - prev_close
                        result['change_pct'] = ((curr_price - prev_close) / prev_close) * 100
                
                return result
            
            return None
            
        except APIError as e:
            self.logger.error(f"API error getting snapshot for {symbol}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting snapshot for {symbol}: {e}")
            return None
    
    def get_market_depth(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get market depth for multiple symbols
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dict mapping symbols to their market depth data
        """
        depth_data = {}
        
        for symbol in symbols:
            try:
                quote = self.get_latest_quote(symbol)
                trade = self.get_latest_trade(symbol)
                
                if quote or trade:
                    depth_data[symbol] = {
                        'quote': quote,
                        'trade': trade,
                        'liquidity_score': self._calculate_liquidity_score(quote),
                        'spread_quality': self._assess_spread_quality(quote)
                    }
                    
            except Exception as e:
                self.logger.error(f"Error getting market depth for {symbol}: {e}")
                continue
        
        return depth_data
    
    def _calculate_liquidity_score(self, quote: Dict) -> float:
        """
        Calculate liquidity score based on bid/ask sizes and spread
        Higher score = better liquidity
        """
        if not quote:
            return 0.0
        
        bid_size = quote.get('bid_size', 0)
        ask_size = quote.get('ask_size', 0)
        spread_pct = quote.get('spread_pct', float('inf'))
        
        # Size score (0-50 points)
        total_size = bid_size + ask_size
        size_score = min(50, total_size / 20)  # Max at 1000 shares
        
        # Spread score (0-50 points)
        if spread_pct < 0.1:
            spread_score = 50
        elif spread_pct < 0.5:
            spread_score = 40
        elif spread_pct < 1.0:
            spread_score = 30
        elif spread_pct < 2.0:
            spread_score = 20
        else:
            spread_score = 10
        
        return size_score + spread_score
    
    def _assess_spread_quality(self, quote: Dict) -> str:
        """Assess spread quality for trading"""
        if not quote:
            return "unknown"
        
        spread_pct = quote.get('spread_pct', float('inf'))
        
        if spread_pct < 0.1:
            return "excellent"
        elif spread_pct < 0.25:
            return "good"
        elif spread_pct < 0.5:
            return "fair"
        elif spread_pct < 1.0:
            return "wide"
        else:
            return "very_wide"
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        try:
            clock = self.api.get_clock()
            return clock.is_open
        except Exception as e:
            self.logger.error(f"Error checking market status: {e}")
            return False
    
    def get_market_calendar(self, start: datetime = None, end: datetime = None) -> List[Dict]:
        """Get market calendar with trading days and hours"""
        self._check_rate_limit()
        
        try:
            if not start:
                start = datetime.now() - timedelta(days=7)
            if not end:
                end = datetime.now() + timedelta(days=7)
            
            calendar = self.api.get_calendar(
                start=start.strftime('%Y-%m-%d'),
                end=end.strftime('%Y-%m-%d')
            )
            
            return [{
                'date': cal.date,
                'open': cal.open,
                'close': cal.close
            } for cal in calendar]
            
        except Exception as e:
            self.logger.error(f"Error getting market calendar: {e}")
            return []


# For testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    # Initialize client
    client = AlpacaClient(paper=True)
    
    # Test symbol
    symbol = "AAPL"
    
    print(f"\n{'='*60}")
    print(f"Testing Alpaca Client with {symbol}")
    print(f"{'='*60}")
    
    # Check market status
    is_open = client.is_market_open()
    print(f"\nMarket Open: {is_open}")
    
    # Get latest quote
    quote = client.get_latest_quote(symbol)
    if quote:
        print(f"\nLatest Quote:")
        print(f"  Bid: ${quote['bid']:.2f} x {quote['bid_size']}")
        print(f"  Ask: ${quote['ask']:.2f} x {quote['ask_size']}")
        print(f"  Spread: ${quote['spread']:.4f} ({quote['spread_pct']:.3f}%)")
    
    # Get latest trade
    trade = client.get_latest_trade(symbol)
    if trade:
        print(f"\nLatest Trade:")
        print(f"  Price: ${trade['price']:.2f}")
        print(f"  Size: {trade['size']} shares")
    
    # Get snapshot
    snapshot = client.get_snapshot(symbol)
    if snapshot:
        print(f"\nSnapshot:")
        if 'daily_stats' in snapshot:
            stats = snapshot['daily_stats']
            print(f"  Day Range: ${stats['low']:.2f} - ${stats['high']:.2f}")
            print(f"  Volume: {stats['volume']:,}")
            if stats.get('vwap'):
                print(f"  VWAP: ${stats['vwap']:.2f}")
    
    print(f"\n{'='*60}\n")