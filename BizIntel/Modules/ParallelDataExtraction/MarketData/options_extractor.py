"""
Options Chain Extractor for SmartReach BizIntel
Extracts options data with Greeks and unusual activity detection
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import pytz
import math

import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm

try:
    from ..base_extractor import BaseExtractor
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from base_extractor import BaseExtractor


class OptionsExtractor(BaseExtractor):
    """Extract options chain data with Greeks and flow analysis"""
    
    # Extractor configuration
    extractor_name = "options"
    required_fields = []
    rate_limit = "2000/hour"
    needs_auth = False
    
    def __init__(self, db_config: Dict = None):
        """Initialize options extractor"""
        super().__init__(db_config)
        
        # Configuration
        self.min_open_interest = 10  # Minimum OI to consider
        self.unusual_volume_ratio = 2.0  # Volume/OI ratio for unusual activity
        self.max_dte_days = 90  # Maximum days to expiration to fetch
        
        # Risk-free rate (approximate US Treasury rate)
        self.risk_free_rate = 0.045  # 4.5% annual
        
        self.logger.info("Options Extractor initialized")
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract options chain data for a company
        
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
        
        self.logger.info(f"Extracting options data for {ticker} ({domain})")
        
        try:
            # Get stock object
            stock = yf.Ticker(ticker)
            
            # Get current stock price for Greeks calculation
            current_price = self._get_current_price(stock)
            if not current_price:
                return {
                    'status': 'failed',
                    'count': 0,
                    'message': f'Could not get current price for {ticker}'
                }
            
            # Get options expiration dates
            expirations = stock.options
            
            if not expirations:
                return {
                    'status': 'skipped',
                    'count': 0,
                    'message': f'No options available for {ticker}'
                }
            
            total_contracts = 0
            unusual_activity = []
            
            # Filter expirations to max DTE
            today = datetime.now()
            filtered_expirations = []
            
            for exp_str in expirations:
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
                dte = (exp_date - today).days
                
                if dte <= self.max_dte_days and dte >= 0:
                    filtered_expirations.append(exp_str)
            
            self.logger.info(f"Processing {len(filtered_expirations)} expiration dates for {ticker}")
            
            # Process each expiration
            for expiration in filtered_expirations:
                try:
                    # Get option chain for this expiration
                    opt_chain = stock.option_chain(expiration)
                    
                    # Process calls
                    if not opt_chain.calls.empty:
                        calls_count, calls_unusual = self._process_options_chain(
                            domain, ticker, opt_chain.calls, expiration, 
                            'call', current_price
                        )
                        total_contracts += calls_count
                        unusual_activity.extend(calls_unusual)
                    
                    # Process puts
                    if not opt_chain.puts.empty:
                        puts_count, puts_unusual = self._process_options_chain(
                            domain, ticker, opt_chain.puts, expiration, 
                            'put', current_price
                        )
                        total_contracts += puts_count
                        unusual_activity.extend(puts_unusual)
                    
                except Exception as e:
                    self.logger.error(f"Error processing expiration {expiration}: {e}")
                    continue
            
            # Calculate aggregate metrics
            if total_contracts > 0:
                put_call_ratio = self._calculate_put_call_ratio(domain, ticker)
                
                self.logger.info(f"Extracted {total_contracts} option contracts for {ticker}")
                
                return {
                    'status': 'success',
                    'count': total_contracts,
                    'message': f'Extracted {total_contracts} option contracts',
                    'data': {
                        'ticker': ticker,
                        'contracts': total_contracts,
                        'expirations': len(filtered_expirations),
                        'unusual_activity': len(unusual_activity),
                        'put_call_ratio': put_call_ratio,
                        'top_unusual': unusual_activity[:5]  # Top 5 unusual
                    }
                }
            else:
                return {
                    'status': 'failed',
                    'count': 0,
                    'message': f'No valid options data for {ticker}'
                }
            
        except Exception as e:
            self.logger.error(f"Options extraction failed for {ticker}: {e}")
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _get_current_price(self, stock: yf.Ticker) -> Optional[float]:
        """Get current stock price"""
        try:
            info = stock.info
            
            # Try different price fields
            for field in ['currentPrice', 'regularMarketPrice', 'previousClose']:
                if field in info and info[field]:
                    return float(info[field])
            
            # Fallback to latest history
            hist = stock.history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return None
    
    def _process_options_chain(self, domain: str, ticker: str, 
                              chain_df: pd.DataFrame, expiration: str,
                              option_type: str, stock_price: float) -> Tuple[int, List]:
        """
        Process a single options chain (calls or puts)
        
        Returns:
            Tuple of (contracts_saved, unusual_activity_list)
        """
        contracts_saved = 0
        unusual_activity = []
        
        # Convert expiration to date
        exp_date = datetime.strptime(expiration, '%Y-%m-%d').date()
        dte = (exp_date - datetime.now().date()).days
        
        # Time to expiration in years for Greeks
        T = max(dte / 365.0, 0.001)  # Avoid division by zero
        
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for _, row in chain_df.iterrows():
                # Skip if no open interest
                open_interest_raw = row.get('openInterest', 0)
                if pd.isna(open_interest_raw):
                    continue
                open_interest = int(float(open_interest_raw))
                if open_interest < self.min_open_interest:
                    continue
                
                # Extract data with proper type conversion
                strike = float(row['strike'])
                
                # Handle volume - can be NaN
                volume_raw = row.get('volume', 0)
                if pd.isna(volume_raw):
                    volume = 0
                else:
                    volume = int(float(volume_raw))
                
                last_price = float(row.get('lastPrice', 0))
                bid = float(row.get('bid', 0))
                ask = float(row.get('ask', 0))
                
                # IV might be numpy.float64
                iv_raw = row.get('impliedVolatility', 0)
                if pd.isna(iv_raw):
                    iv = 0
                else:
                    iv = float(iv_raw)
                
                # Contract symbol
                contract_symbol = row.get('contractSymbol', f"{ticker}{expiration}{option_type[0].upper()}{strike}")
                
                # Calculate volume/OI ratio
                volume_oi_ratio = volume / open_interest if open_interest > 0 else 0
                
                # Detect unusual activity
                if volume_oi_ratio > self.unusual_volume_ratio and volume > 100:
                    unusual_activity.append({
                        'contract': contract_symbol,
                        'strike': strike,
                        'type': option_type,
                        'expiration': expiration,
                        'volume': volume,
                        'open_interest': open_interest,
                        'ratio': volume_oi_ratio,
                        'premium': last_price * volume * 100  # Total premium
                    })
                
                # Calculate Greeks
                greeks = self._calculate_greeks(
                    stock_price, strike, T, self.risk_free_rate, iv, option_type
                )
                
                # Determine moneyness
                if option_type == 'call':
                    in_the_money = stock_price > strike
                else:  # put
                    in_the_money = stock_price < strike
                
                moneyness = (stock_price - strike) / strike
                
                # Save to database - ensure all values are Python native types
                cursor.execute("""
                    INSERT INTO options_data 
                    (time, company_domain, ticker, expiration_date, strike_price, 
                     option_type, contract_symbol, last_price, bid, ask, 
                     volume, open_interest, volume_oi_ratio,
                     implied_volatility, delta, gamma, theta, vega,
                     in_the_money, moneyness, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, time, contract_symbol) 
                    DO UPDATE SET
                        last_price = EXCLUDED.last_price,
                        bid = EXCLUDED.bid,
                        ask = EXCLUDED.ask,
                        volume = EXCLUDED.volume,
                        open_interest = EXCLUDED.open_interest,
                        volume_oi_ratio = EXCLUDED.volume_oi_ratio
                """, (
                    datetime.now(pytz.UTC),
                    domain,
                    ticker,
                    exp_date,
                    float(strike),
                    option_type,
                    contract_symbol,
                    float(last_price) if last_price > 0 else None,
                    float(bid) if bid > 0 else None,
                    float(ask) if ask > 0 else None,
                    int(volume),
                    int(open_interest),
                    float(volume_oi_ratio),
                    float(iv) if iv > 0 else None,
                    float(greeks['delta']),
                    float(greeks['gamma']),
                    float(greeks['theta']),
                    float(greeks['vega']),
                    bool(in_the_money),
                    float(moneyness),
                    'yahoo'
                ))
                
                if cursor.rowcount > 0:
                    contracts_saved += 1
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error saving options data: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        # Sort unusual activity by ratio
        unusual_activity.sort(key=lambda x: x['ratio'], reverse=True)
        
        return contracts_saved, unusual_activity
    
    def _calculate_greeks(self, S: float, K: float, T: float, r: float, 
                         sigma: float, option_type: str) -> Dict[str, float]:
        """
        Calculate option Greeks using Black-Scholes model
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Implied volatility
            option_type: 'call' or 'put'
        """
        # Handle edge cases
        if sigma <= 0 or T <= 0:
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0
            }
        
        try:
            # Calculate d1 and d2
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            # Calculate Greeks
            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T)) 
                        - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
            else:  # put
                delta = norm.cdf(d1) - 1
                theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T)) 
                        + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
            
            gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
            vega = S * norm.pdf(d1) * math.sqrt(T) / 100  # Divide by 100 for 1% move
            
            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 4),
                'theta': round(theta, 4),
                'vega': round(vega, 4)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating Greeks: {e}")
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0
            }
    
    def _calculate_put_call_ratio(self, domain: str, ticker: str) -> Optional[float]:
        """Calculate put/call ratio for today's options"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get today's put and call volumes
            cursor.execute("""
                SELECT 
                    option_type,
                    SUM(volume) as total_volume
                FROM options_data
                WHERE ticker = %s
                  AND time > NOW() - INTERVAL '1 day'
                GROUP BY option_type
            """, (ticker,))
            
            results = cursor.fetchall()
            
            if results:
                volumes = {row[0]: row[1] for row in results}
                call_volume = volumes.get('call', 0)
                put_volume = volumes.get('put', 0)
                
                if call_volume > 0:
                    return round(put_volume / call_volume, 3)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating put/call ratio: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def detect_smart_money_flow(self, ticker: str, lookback_days: int = 5) -> Dict:
        """
        Detect potential smart money options flow
        
        Looks for:
        - Large volume relative to open interest
        - Trades near ask (buying pressure)
        - Concentrated strikes/expirations
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Find unusual activity
            cursor.execute("""
                SELECT 
                    contract_symbol,
                    strike_price,
                    expiration_date,
                    option_type,
                    volume,
                    open_interest,
                    volume_oi_ratio,
                    last_price,
                    bid,
                    ask,
                    (last_price - bid) / (ask - bid) as trade_aggression
                FROM options_data
                WHERE ticker = %s
                  AND time > NOW() - INTERVAL '%s days'
                  AND volume_oi_ratio > %s
                  AND volume > 100
                ORDER BY volume_oi_ratio DESC
                LIMIT 20
            """, (ticker, lookback_days, self.unusual_volume_ratio))
            
            unusual_flows = cursor.fetchall()
            
            if unusual_flows:
                smart_money_signals = []
                
                for flow in unusual_flows:
                    # Check if trade was aggressive (near ask)
                    aggression = flow[10] if flow[10] else 0
                    
                    signal = {
                        'contract': flow[0],
                        'strike': float(flow[1]),
                        'expiration': flow[2],
                        'type': flow[3],
                        'volume': int(flow[4]),
                        'open_interest': int(flow[5]),
                        'ratio': float(flow[6]),
                        'premium': float(flow[7]) * int(flow[4]) * 100,
                        'aggressive': aggression > 0.7  # Near ask
                    }
                    
                    smart_money_signals.append(signal)
                
                return {
                    'signals_found': len(smart_money_signals),
                    'top_signals': smart_money_signals[:5],
                    'total_premium': sum(s['premium'] for s in smart_money_signals)
                }
            
            return {'signals_found': 0, 'top_signals': [], 'total_premium': 0}
            
        except Exception as e:
            self.logger.error(f"Error detecting smart money flow: {e}")
            return {'signals_found': 0, 'top_signals': [], 'total_premium': 0}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


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
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "NVAX"
    
    # Create test company data
    company_data = {
        'domain': f'{test_ticker.lower()}.com',
        'ticker': test_ticker,
        'name': f'Test extraction for {test_ticker}'
    }
    
    print(f"\n{'='*60}")
    print(f"Testing Options Extractor with {test_ticker}")
    print(f"{'='*60}")
    
    # Create extractor and run
    extractor = OptionsExtractor(db_config)
    result = extractor.extract(company_data)
    
    print(f"\nExtraction Result:")
    print(json.dumps(result, indent=2, default=str))
    
    # If successful, check for smart money flow
    if result['status'] == 'success':
        smart_money = extractor.detect_smart_money_flow(test_ticker)
        print(f"\nSmart Money Flow Detection:")
        print(json.dumps(smart_money, indent=2, default=str))
    
    print(f"\n{'='*60}\n")