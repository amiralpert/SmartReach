"""
System 1 Market Analyzer
Performs technical analysis, pattern detection, and event identification
Part of Week 3 Market Data Enhancement
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import talib
from dataclasses import dataclass
from enum import Enum
import json
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# DATA CLASSES AND ENUMS
# ============================================

class PatternType(Enum):
    BREAKOUT = "breakout"
    SQUEEZE = "squeeze"
    DIVERGENCE = "divergence"
    REVERSAL = "reversal"
    CONTINUATION = "continuation"

class EventType(Enum):
    STRUCTURAL_BREAK = "structural_break"
    REGIME_CHANGE = "regime_change"
    VOLATILITY_SPIKE = "volatility_spike"
    VOLUME_SURGE = "volume_surge"
    TREND_CHANGE = "trend_change"

class SignalDirection(Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

@dataclass
class TechnicalIndicators:
    """Holds calculated technical indicators"""
    ticker: str
    timestamp: datetime
    # Moving averages
    sma_20: float
    sma_50: float
    sma_200: float
    ema_12: float
    ema_26: float
    # Momentum
    rsi_14: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    stochastic_k: float
    stochastic_d: float
    # Volatility
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    bollinger_width: float
    atr_14: float
    # Volume
    obv: int
    vwap: float
    volume_sma_20: int
    volume_ratio: float
    # Support/Resistance
    pivot_point: float
    resistance_1: float
    resistance_2: float
    support_1: float
    support_2: float

@dataclass
class Pattern:
    """Represents a detected pattern"""
    pattern_type: PatternType
    pattern_name: str
    start_timestamp: datetime
    end_timestamp: datetime
    confidence_score: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    is_bullish: bool
    pattern_strength: str

@dataclass
class MarketEvent:
    """Represents a detected market event"""
    event_type: EventType
    event_name: str
    detection_timestamp: datetime
    event_timestamp: datetime
    significance_score: float
    price_impact: float
    volume_impact: float
    volatility_impact: float


# ============================================
# MARKET ANALYZER CLASS
# ============================================

class MarketAnalyzer:
    """
    System 1 Market Analyzer
    Analyzes market data to generate technical signals and detect patterns
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize Market Analyzer
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self.parameters = None
        self._connect_db()
        self._load_parameters()
        
    def _connect_db(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.db_config['host'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def _load_parameters(self):
        """Load analysis parameters from database"""
        try:
            query = """
                SELECT technical_params, pattern_params, event_params, 
                       options_params, composite_params
                FROM systemuno_market.analysis_parameters
                WHERE parameter_set_name = 'default' 
                AND is_active = true
                ORDER BY version DESC
                LIMIT 1
            """
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            
            if result:
                self.parameters = {
                    'technical': result['technical_params'],
                    'pattern': result['pattern_params'],
                    'event': result['event_params'],
                    'options': result['options_params'],
                    'composite': result['composite_params']
                }
                logger.info("Parameters loaded successfully")
            else:
                logger.warning("No active parameters found, using defaults")
                self._use_default_parameters()
                
        except Exception as e:
            logger.error(f"Failed to load parameters: {e}")
            self._use_default_parameters()
            
    def _use_default_parameters(self):
        """Use default parameters if database load fails"""
        self.parameters = {
            'technical': {
                'rsi_period': 14,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'bollinger_period': 20,
                'bollinger_std': 2,
                'atr_period': 14
            },
            'pattern': {
                'min_pattern_bars': 5,
                'breakout_volume_multiplier': 1.5,
                'min_confidence_score': 60
            },
            'event': {
                'significance_level': 0.05,
                'min_event_magnitude': 2.0
            },
            'options': {
                'unusual_activity_threshold': 2.0,
                'min_premium_flow': 100000
            },
            'composite': {
                'technical_weight': 0.3,
                'pattern_weight': 0.25,
                'options_weight': 0.3,
                'event_weight': 0.15
            }
        }
    
    # ============================================
    # TECHNICAL INDICATORS
    # ============================================
    
    def calculate_technical_indicators(self, ticker: str, 
                                      company_domain: str,
                                      lookback_days: int = 100) -> List[TechnicalIndicators]:
        """
        Calculate technical indicators for a ticker
        
        Args:
            ticker: Stock ticker symbol
            company_domain: Company domain
            lookback_days: Number of days to analyze
            
        Returns:
            List of TechnicalIndicators objects
        """
        try:
            # Fetch market data
            market_data = self._fetch_market_data(ticker, company_domain, lookback_days)
            
            if len(market_data) < 30:
                logger.warning(f"Insufficient data for {ticker}: {len(market_data)} rows")
                return []
            
            # Convert to DataFrame
            df = pd.DataFrame(market_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate indicators
            indicators = self._calculate_all_indicators(df, ticker)
            
            # Store in database
            self._store_technical_indicators(indicators, company_domain)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {ticker}: {e}")
            return []
    
    def _fetch_market_data(self, ticker: str, company_domain: str, 
                          lookback_days: int) -> List[Dict]:
        """Fetch historical market data"""
        try:
            # Rollback any failed transaction
            if self.conn.status != psycopg2.extensions.STATUS_READY:
                self.conn.rollback()
            
            query = """
                SELECT time as timestamp, open, high, low, close, volume
                FROM market.market_data
                WHERE ticker = %s 
                AND company_domain = %s
                AND time >= %s
                ORDER BY time
            """
            
            start_date = datetime.now() - timedelta(days=lookback_days)
            self.cursor.execute(query, (ticker, company_domain, start_date))
            
            return self.cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            self.conn.rollback()
            return []
    
    def _calculate_all_indicators(self, df: pd.DataFrame, ticker: str) -> List[TechnicalIndicators]:
        """Calculate all technical indicators"""
        indicators_list = []
        
        # Extract price and volume arrays
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Moving Averages
        sma_20 = talib.SMA(close, timeperiod=20)
        sma_50 = talib.SMA(close, timeperiod=50)
        sma_200 = talib.SMA(close, timeperiod=200)
        ema_12 = talib.EMA(close, timeperiod=12)
        ema_26 = talib.EMA(close, timeperiod=26)
        
        # Momentum Indicators
        rsi_14 = talib.RSI(close, timeperiod=self.parameters['technical']['rsi_period'])
        macd_line, macd_signal, macd_hist = talib.MACD(
            close,
            fastperiod=self.parameters['technical']['macd_fast'],
            slowperiod=self.parameters['technical']['macd_slow'],
            signalperiod=self.parameters['technical']['macd_signal']
        )
        stoch_k, stoch_d = talib.STOCH(high, low, close)
        
        # Volatility Indicators
        bb_upper, bb_middle, bb_lower = talib.BBANDS(
            close,
            timeperiod=self.parameters['technical']['bollinger_period'],
            nbdevup=self.parameters['technical']['bollinger_std'],
            nbdevdn=self.parameters['technical']['bollinger_std']
        )
        bb_width = bb_upper - bb_lower
        atr_14 = talib.ATR(high, low, close, timeperiod=self.parameters['technical']['atr_period'])
        
        # Volume Indicators
        obv = talib.OBV(close, volume)
        volume_sma_20 = talib.SMA(volume, timeperiod=20)
        
        # VWAP calculation
        vwap = self._calculate_vwap(df)
        
        # Support/Resistance (Pivot Points)
        pivot_points = self._calculate_pivot_points(high, low, close)
        
        # Create TechnicalIndicators objects for the last 20 periods
        for i in range(max(200, len(df) - 20), len(df)):
            if pd.isna(sma_200[i]):  # Skip if we don't have enough data
                continue
                
            volume_ratio = volume[i] / volume_sma_20[i] if volume_sma_20[i] > 0 else 0
            
            indicators = TechnicalIndicators(
                ticker=ticker,
                timestamp=df.iloc[i]['timestamp'],
                sma_20=float(sma_20[i]),
                sma_50=float(sma_50[i]),
                sma_200=float(sma_200[i]),
                ema_12=float(ema_12[i]),
                ema_26=float(ema_26[i]),
                rsi_14=float(rsi_14[i]) if not pd.isna(rsi_14[i]) else 50.0,
                macd_line=float(macd_line[i]) if not pd.isna(macd_line[i]) else 0.0,
                macd_signal=float(macd_signal[i]) if not pd.isna(macd_signal[i]) else 0.0,
                macd_histogram=float(macd_hist[i]) if not pd.isna(macd_hist[i]) else 0.0,
                stochastic_k=float(stoch_k[i]) if not pd.isna(stoch_k[i]) else 50.0,
                stochastic_d=float(stoch_d[i]) if not pd.isna(stoch_d[i]) else 50.0,
                bollinger_upper=float(bb_upper[i]),
                bollinger_middle=float(bb_middle[i]),
                bollinger_lower=float(bb_lower[i]),
                bollinger_width=float(bb_width[i]),
                atr_14=float(atr_14[i]) if not pd.isna(atr_14[i]) else 0.0,
                obv=int(obv[i]) if not pd.isna(obv[i]) else 0,
                vwap=float(vwap[i]) if i < len(vwap) else close[i],
                volume_sma_20=int(volume_sma_20[i]) if not pd.isna(volume_sma_20[i]) else 0,
                volume_ratio=float(volume_ratio),
                pivot_point=float(pivot_points['pivot'][i]),
                resistance_1=float(pivot_points['r1'][i]),
                resistance_2=float(pivot_points['r2'][i]),
                support_1=float(pivot_points['s1'][i]),
                support_2=float(pivot_points['s2'][i])
            )
            indicators_list.append(indicators)
        
        return indicators_list
    
    def _calculate_vwap(self, df: pd.DataFrame) -> np.ndarray:
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        cumulative_tpv = (typical_price * df['volume']).cumsum()
        cumulative_volume = df['volume'].cumsum()
        vwap = cumulative_tpv / cumulative_volume
        return vwap.values
    
    def _calculate_pivot_points(self, high: np.ndarray, low: np.ndarray, 
                               close: np.ndarray) -> Dict[str, np.ndarray]:
        """Calculate pivot points and support/resistance levels"""
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        
        return {
            'pivot': pivot,
            'r1': r1,
            'r2': r2,
            's1': s1,
            's2': s2
        }
    
    def _store_technical_indicators(self, indicators: List[TechnicalIndicators], 
                                   company_domain: str):
        """Store technical indicators in database"""
        if not indicators:
            return
            
        try:
            # Prepare batch insert
            values = []
            for ind in indicators:
                values.append((
                    company_domain, ind.ticker, ind.timestamp,
                    ind.sma_20, ind.sma_50, ind.sma_200, ind.ema_12, ind.ema_26,
                    ind.rsi_14, ind.macd_line, ind.macd_signal, ind.macd_histogram,
                    ind.stochastic_k, ind.stochastic_d,
                    ind.bollinger_upper, ind.bollinger_middle, ind.bollinger_lower,
                    ind.bollinger_width, ind.atr_14,
                    ind.obv, ind.vwap, ind.volume_sma_20, ind.volume_ratio,
                    ind.pivot_point, ind.resistance_1, ind.resistance_2,
                    ind.support_1, ind.support_2,
                    '1.0.0'  # calculation_version
                ))
            
            # Insert with ON CONFLICT DO UPDATE
            query = """
                INSERT INTO systemuno_market.technical_indicators (
                    company_domain, ticker, timestamp,
                    sma_20, sma_50, sma_200, ema_12, ema_26,
                    rsi_14, macd_line, macd_signal, macd_histogram,
                    stochastic_k, stochastic_d,
                    bollinger_upper, bollinger_middle, bollinger_lower,
                    bollinger_width, atr_14,
                    obv, vwap, volume_sma_20, volume_ratio,
                    pivot_point, resistance_1, resistance_2,
                    support_1, support_2,
                    calculation_version
                ) VALUES %s
                ON CONFLICT (company_domain, ticker, timestamp) 
                DO UPDATE SET
                    sma_20 = EXCLUDED.sma_20,
                    sma_50 = EXCLUDED.sma_50,
                    sma_200 = EXCLUDED.sma_200,
                    rsi_14 = EXCLUDED.rsi_14,
                    macd_line = EXCLUDED.macd_line,
                    vwap = EXCLUDED.vwap,
                    volume_ratio = EXCLUDED.volume_ratio
            """
            
            from psycopg2.extras import execute_values
            execute_values(self.cursor, query, values)
            self.conn.commit()
            
            logger.info(f"Stored {len(indicators)} technical indicators")
            
        except Exception as e:
            logger.error(f"Failed to store technical indicators: {e}")
            self.conn.rollback()
    
    # ============================================
    # PATTERN DETECTION
    # ============================================
    
    def detect_patterns(self, ticker: str, company_domain: str) -> List[Pattern]:
        """
        Detect technical patterns in price data
        
        Args:
            ticker: Stock ticker symbol
            company_domain: Company domain
            
        Returns:
            List of detected Pattern objects
        """
        patterns = []
        
        try:
            # Get recent indicators
            indicators = self._get_recent_indicators(ticker, company_domain, days=20)
            
            if len(indicators) < 10:
                logger.warning(f"Insufficient data for pattern detection: {ticker}")
                return []
            
            # Detect various patterns
            patterns.extend(self._detect_breakout_patterns(indicators, ticker))
            patterns.extend(self._detect_squeeze_patterns(indicators, ticker))
            patterns.extend(self._detect_divergence_patterns(indicators, ticker))
            
            # Store patterns in database
            self._store_patterns(patterns, company_domain, ticker)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect patterns for {ticker}: {e}")
            return []
    
    def _get_recent_indicators(self, ticker: str, company_domain: str, 
                              days: int) -> pd.DataFrame:
        """Get recent technical indicators from database"""
        try:
            # Rollback any failed transaction
            if self.conn.status != psycopg2.extensions.STATUS_READY:
                self.conn.rollback()
            
            query = """
                SELECT *, close FROM systemuno_market.technical_indicators mti
                JOIN market.market_data md ON md.ticker = mti.ticker 
                    AND md.company_domain = mti.company_domain 
                    AND DATE(md.time) = DATE(mti.timestamp)
                WHERE mti.ticker = %s 
                AND mti.company_domain = %s
                AND mti.timestamp >= %s
                ORDER BY mti.timestamp
            """
            
            start_date = datetime.now() - timedelta(days=days)
            self.cursor.execute(query, (ticker, company_domain, start_date))
            
            results = self.cursor.fetchall()
            return pd.DataFrame(results) if results else pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Failed to get recent indicators: {e}")
            self.conn.rollback()
            return pd.DataFrame()
    
    def _detect_breakout_patterns(self, indicators: pd.DataFrame, 
                                 ticker: str) -> List[Pattern]:
        """Detect breakout patterns"""
        patterns = []
        
        if len(indicators) < 5:
            return patterns
        
        # Bollinger Band Breakout
        latest = indicators.iloc[-1]
        recent = indicators.tail(5)
        
        # Check for upper band breakout
        if (latest['close'] > latest['bollinger_upper'] and 
            latest['volume_ratio'] > self.parameters['pattern']['breakout_volume_multiplier']):
            
            pattern = Pattern(
                pattern_type=PatternType.BREAKOUT,
                pattern_name="Bollinger Band Upper Breakout",
                start_timestamp=recent.iloc[0]['timestamp'],
                end_timestamp=latest['timestamp'],
                confidence_score=self._calculate_breakout_confidence(recent),
                entry_price=float(latest['close']),
                target_price=float(latest['close'] * 1.05),  # 5% target
                stop_loss=float(latest['bollinger_middle']),
                risk_reward_ratio=self._calculate_risk_reward(
                    latest['close'], 
                    latest['close'] * 1.05,
                    latest['bollinger_middle']
                ),
                is_bullish=True,
                pattern_strength="strong" if latest['rsi_14'] > 60 else "moderate"
            )
            patterns.append(pattern)
        
        # Check for support breakout (bearish)
        if (latest['close'] < latest['support_1'] and 
            latest['volume_ratio'] > self.parameters['pattern']['breakout_volume_multiplier']):
            
            pattern = Pattern(
                pattern_type=PatternType.BREAKOUT,
                pattern_name="Support Level Breakout",
                start_timestamp=recent.iloc[0]['timestamp'],
                end_timestamp=latest['timestamp'],
                confidence_score=self._calculate_breakout_confidence(recent),
                entry_price=float(latest['close']),
                target_price=float(latest['support_2']),
                stop_loss=float(latest['pivot_point']),
                risk_reward_ratio=self._calculate_risk_reward(
                    latest['close'],
                    latest['support_2'],
                    latest['pivot_point']
                ),
                is_bullish=False,
                pattern_strength="strong" if latest['rsi_14'] < 40 else "moderate"
            )
            patterns.append(pattern)
        
        return patterns
    
    def _detect_squeeze_patterns(self, indicators: pd.DataFrame, 
                                ticker: str) -> List[Pattern]:
        """Detect squeeze patterns (Bollinger Band squeeze)"""
        patterns = []
        
        if len(indicators) < 10:
            return patterns
        
        recent = indicators.tail(10)
        latest = indicators.iloc[-1]
        
        # Calculate Bollinger Band width percentile
        bb_width_pct = (latest['bollinger_width'] / latest['bollinger_middle']) * 100
        
        # Detect squeeze if BB width is very narrow
        if bb_width_pct < 5:  # Less than 5% of price
            pattern = Pattern(
                pattern_type=PatternType.SQUEEZE,
                pattern_name="Bollinger Band Squeeze",
                start_timestamp=recent.iloc[0]['timestamp'],
                end_timestamp=latest['timestamp'],
                confidence_score=70.0,  # Higher confidence for tighter squeeze
                entry_price=float(latest['close']),
                target_price=float(latest['close'] * 1.08),  # 8% move expected
                stop_loss=float(latest['close'] * 0.97),  # 3% stop
                risk_reward_ratio=2.67,
                is_bullish=latest['rsi_14'] > 50,  # Direction based on RSI
                pattern_strength="strong" if bb_width_pct < 3 else "moderate"
            )
            patterns.append(pattern)
        
        return patterns
    
    def _detect_divergence_patterns(self, indicators: pd.DataFrame, 
                                   ticker: str) -> List[Pattern]:
        """Detect divergence patterns between price and indicators"""
        patterns = []
        
        if len(indicators) < 14:
            return patterns
        
        recent = indicators.tail(14)
        
        # Find price highs and lows
        price_highs = recent['close'].rolling(window=3).max()
        price_lows = recent['close'].rolling(window=3).min()
        
        # Check for bullish divergence (price makes lower low, RSI makes higher low)
        if len(recent) >= 2:
            if (recent.iloc[-1]['close'] < recent.iloc[-7]['close'] and
                recent.iloc[-1]['rsi_14'] > recent.iloc[-7]['rsi_14'] and
                recent.iloc[-1]['rsi_14'] < 30):
                
                pattern = Pattern(
                    pattern_type=PatternType.DIVERGENCE,
                    pattern_name="Bullish RSI Divergence",
                    start_timestamp=recent.iloc[-7]['timestamp'],
                    end_timestamp=recent.iloc[-1]['timestamp'],
                    confidence_score=65.0,
                    entry_price=float(recent.iloc[-1]['close']),
                    target_price=float(recent.iloc[-1]['close'] * 1.06),
                    stop_loss=float(recent.iloc[-1]['close'] * 0.97),
                    risk_reward_ratio=2.0,
                    is_bullish=True,
                    pattern_strength="moderate"
                )
                patterns.append(pattern)
        
        # Check for bearish divergence (price makes higher high, RSI makes lower high)
        if len(recent) >= 2:
            if (recent.iloc[-1]['close'] > recent.iloc[-7]['close'] and
                recent.iloc[-1]['rsi_14'] < recent.iloc[-7]['rsi_14'] and
                recent.iloc[-1]['rsi_14'] > 70):
                
                pattern = Pattern(
                    pattern_type=PatternType.DIVERGENCE,
                    pattern_name="Bearish RSI Divergence",
                    start_timestamp=recent.iloc[-7]['timestamp'],
                    end_timestamp=recent.iloc[-1]['timestamp'],
                    confidence_score=65.0,
                    entry_price=float(recent.iloc[-1]['close']),
                    target_price=float(recent.iloc[-1]['close'] * 0.94),
                    stop_loss=float(recent.iloc[-1]['close'] * 1.03),
                    risk_reward_ratio=2.0,
                    is_bullish=False,
                    pattern_strength="moderate"
                )
                patterns.append(pattern)
        
        return patterns
    
    def _calculate_breakout_confidence(self, recent_data: pd.DataFrame) -> float:
        """Calculate confidence score for breakout pattern"""
        confidence = 50.0
        
        # Volume confirmation
        if recent_data.iloc[-1]['volume_ratio'] > 2.0:
            confidence += 20
        elif recent_data.iloc[-1]['volume_ratio'] > 1.5:
            confidence += 10
        
        # RSI confirmation
        if recent_data.iloc[-1]['rsi_14'] > 60:
            confidence += 10
        elif recent_data.iloc[-1]['rsi_14'] < 40:
            confidence += 10
        
        # MACD confirmation
        if recent_data.iloc[-1]['macd_histogram'] > 0:
            confidence += 10
        
        return min(confidence, 100.0)
    
    def _calculate_risk_reward(self, entry: float, target: float, stop: float) -> float:
        """Calculate risk/reward ratio"""
        risk = abs(entry - stop)
        reward = abs(target - entry)
        return reward / risk if risk > 0 else 0
    
    def _store_patterns(self, patterns: List[Pattern], company_domain: str, ticker: str):
        """Store detected patterns in database"""
        if not patterns:
            return
            
        try:
            for pattern in patterns:
                query = """
                    INSERT INTO systemuno_market.patterns (
                        company_domain, ticker, pattern_type, pattern_name,
                        start_timestamp, end_timestamp, confidence_score,
                        entry_price, target_price, stop_loss, risk_reward_ratio,
                        volume_confirmation, is_bullish, pattern_strength,
                        pattern_metadata, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                values = (
                    company_domain, ticker, pattern.pattern_type.value, pattern.pattern_name,
                    pattern.start_timestamp, pattern.end_timestamp, pattern.confidence_score,
                    pattern.entry_price, pattern.target_price, pattern.stop_loss,
                    pattern.risk_reward_ratio, True, pattern.is_bullish,
                    pattern.pattern_strength, json.dumps({}), 'active'
                )
                
                self.cursor.execute(query, values)
            
            self.conn.commit()
            logger.info(f"Stored {len(patterns)} patterns for {ticker}")
            
        except Exception as e:
            logger.error(f"Failed to store patterns: {e}")
            self.conn.rollback()
    
    # ============================================
    # EVENT DETECTION
    # ============================================
    
    def detect_events(self, ticker: str, company_domain: str) -> List[MarketEvent]:
        """
        Detect market events and regime changes
        
        Args:
            ticker: Stock ticker symbol
            company_domain: Company domain
            
        Returns:
            List of detected MarketEvent objects
        """
        events = []
        
        try:
            # Get recent data
            indicators = self._get_recent_indicators(ticker, company_domain, days=30)
            
            if len(indicators) < 20:
                logger.warning(f"Insufficient data for event detection: {ticker}")
                return []
            
            # Detect various events
            events.extend(self._detect_volatility_events(indicators, ticker))
            events.extend(self._detect_volume_events(indicators, ticker))
            events.extend(self._detect_trend_changes(indicators, ticker))
            
            # Store events in database
            self._store_events(events, company_domain, ticker)
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to detect events for {ticker}: {e}")
            return []
    
    def _detect_volatility_events(self, indicators: pd.DataFrame, 
                                 ticker: str) -> List[MarketEvent]:
        """Detect volatility spike events"""
        events = []
        
        if len(indicators) < 20:
            return events
        
        # Calculate volatility percentile
        recent_atr = indicators['atr_14'].tail(20)
        current_atr = indicators.iloc[-1]['atr_14']
        atr_percentile = (recent_atr < current_atr).sum() / len(recent_atr) * 100
        
        # Detect volatility spike
        if atr_percentile > 90:
            event = MarketEvent(
                event_type=EventType.VOLATILITY_SPIKE,
                event_name="High Volatility Detected",
                detection_timestamp=datetime.now(),
                event_timestamp=indicators.iloc[-1]['timestamp'],
                significance_score=float(atr_percentile),
                price_impact=float(current_atr / indicators.iloc[-1]['close'] * 100),
                volume_impact=0.0,
                volatility_impact=float((current_atr / recent_atr.mean() - 1) * 100)
            )
            events.append(event)
        
        return events
    
    def _detect_volume_events(self, indicators: pd.DataFrame, 
                             ticker: str) -> List[MarketEvent]:
        """Detect volume surge events"""
        events = []
        
        latest = indicators.iloc[-1]
        
        # Detect volume surge
        if latest['volume_ratio'] > 3.0:
            event = MarketEvent(
                event_type=EventType.VOLUME_SURGE,
                event_name="Extreme Volume Surge",
                detection_timestamp=datetime.now(),
                event_timestamp=latest['timestamp'],
                significance_score=min(latest['volume_ratio'] * 20, 100),
                price_impact=0.0,
                volume_impact=float((latest['volume_ratio'] - 1) * 100),
                volatility_impact=0.0
            )
            events.append(event)
        
        return events
    
    def _detect_trend_changes(self, indicators: pd.DataFrame, 
                             ticker: str) -> List[MarketEvent]:
        """Detect trend change events"""
        events = []
        
        if len(indicators) < 10:
            return events
        
        recent = indicators.tail(10)
        latest = indicators.iloc[-1]
        
        # Golden Cross (50 SMA crosses above 200 SMA)
        if (latest['sma_50'] > latest['sma_200'] and
            recent.iloc[-2]['sma_50'] <= recent.iloc[-2]['sma_200']):
            
            event = MarketEvent(
                event_type=EventType.TREND_CHANGE,
                event_name="Golden Cross",
                detection_timestamp=datetime.now(),
                event_timestamp=latest['timestamp'],
                significance_score=85.0,
                price_impact=5.0,  # Expected 5% move
                volume_impact=0.0,
                volatility_impact=0.0
            )
            events.append(event)
        
        # Death Cross (50 SMA crosses below 200 SMA)
        if (latest['sma_50'] < latest['sma_200'] and
            recent.iloc[-2]['sma_50'] >= recent.iloc[-2]['sma_200']):
            
            event = MarketEvent(
                event_type=EventType.TREND_CHANGE,
                event_name="Death Cross",
                detection_timestamp=datetime.now(),
                event_timestamp=latest['timestamp'],
                significance_score=85.0,
                price_impact=-5.0,  # Expected -5% move
                volume_impact=0.0,
                volatility_impact=0.0
            )
            events.append(event)
        
        return events
    
    def _store_events(self, events: List[MarketEvent], company_domain: str, ticker: str):
        """Store detected events in database"""
        if not events:
            return
            
        try:
            for event in events:
                query = """
                    INSERT INTO systemuno_market.events (
                        company_domain, ticker, event_type, event_name,
                        detection_timestamp, event_timestamp,
                        significance_score, price_impact, volume_impact,
                        volatility_impact, pre_event_trend, post_event_trend,
                        event_metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                values = (
                    company_domain, ticker, event.event_type.value, event.event_name,
                    event.detection_timestamp, event.event_timestamp,
                    event.significance_score, event.price_impact,
                    event.volume_impact, event.volatility_impact,
                    'unknown', 'unknown', json.dumps({})
                )
                
                self.cursor.execute(query, values)
            
            self.conn.commit()
            logger.info(f"Stored {len(events)} events for {ticker}")
            
        except Exception as e:
            logger.error(f"Failed to store events: {e}")
            self.conn.rollback()
    
    # ============================================
    # COMPOSITE SIGNAL GENERATION
    # ============================================
    
    def generate_composite_signal(self, ticker: str, company_domain: str) -> Dict:
        """
        Generate composite trading signal combining all analyses
        
        Args:
            ticker: Stock ticker symbol
            company_domain: Company domain
            
        Returns:
            Dictionary containing composite signal
        """
        try:
            # Get latest data
            latest_indicators = self._get_latest_indicators(ticker, company_domain)
            active_patterns = self._get_active_patterns(ticker, company_domain)
            recent_events = self._get_recent_events(ticker, company_domain)
            options_flow = self._get_options_flow(ticker, company_domain)
            
            # Calculate component scores
            technical_score = self._calculate_technical_score(latest_indicators)
            pattern_score = self._calculate_pattern_score(active_patterns)
            event_score = self._calculate_event_score(recent_events)
            options_score = self._calculate_options_score(options_flow)
            
            # Weight and combine scores
            weights = self.parameters['composite']
            
            bullish_score = (
                technical_score['bullish'] * weights['technical_weight'] +
                pattern_score['bullish'] * weights['pattern_weight'] +
                event_score['bullish'] * weights['event_weight'] +
                options_score['bullish'] * weights['options_weight']
            )
            
            bearish_score = (
                technical_score['bearish'] * weights['technical_weight'] +
                pattern_score['bearish'] * weights['pattern_weight'] +
                event_score['bearish'] * weights['event_weight'] +
                options_score['bearish'] * weights['options_weight']
            )
            
            # Determine signal direction
            signal_direction = self._determine_signal_direction(bullish_score, bearish_score)
            
            # Calculate confidence
            confidence_score = abs(bullish_score - bearish_score)
            
            # Prepare composite signal
            composite_signal = {
                'ticker': ticker,
                'company_domain': company_domain,
                'timestamp': datetime.now(),
                'bullish_score': bullish_score,
                'bearish_score': bearish_score,
                'confidence_score': confidence_score,
                'signal_direction': signal_direction.value,
                'components': {
                    'technical': technical_score,
                    'patterns': pattern_score,
                    'events': event_score,
                    'options': options_score
                }
            }
            
            # Store in database
            self._store_composite_signal(composite_signal)
            
            return composite_signal
            
        except Exception as e:
            logger.error(f"Failed to generate composite signal for {ticker}: {e}")
            return {}
    
    def _get_latest_indicators(self, ticker: str, company_domain: str) -> Dict:
        """Get latest technical indicators"""
        try:
            query = """
                SELECT * FROM systemuno_market.technical_indicators
                WHERE ticker = %s AND company_domain = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """
            self.cursor.execute(query, (ticker, company_domain))
            return self.cursor.fetchone() or {}
        except Exception as e:
            logger.error(f"Failed to get latest indicators: {e}")
            return {}
    
    def _get_active_patterns(self, ticker: str, company_domain: str) -> List[Dict]:
        """Get active patterns"""
        try:
            query = """
                SELECT * FROM systemuno_market.patterns
                WHERE ticker = %s AND company_domain = %s
                AND status = 'active'
                ORDER BY confidence_score DESC
            """
            self.cursor.execute(query, (ticker, company_domain))
            return self.cursor.fetchall() or []
        except Exception as e:
            logger.error(f"Failed to get active patterns: {e}")
            return []
    
    def _get_recent_events(self, ticker: str, company_domain: str) -> List[Dict]:
        """Get recent market events"""
        try:
            query = """
                SELECT * FROM systemuno_market.events
                WHERE ticker = %s AND company_domain = %s
                AND event_timestamp >= %s
                ORDER BY significance_score DESC
            """
            cutoff = datetime.now() - timedelta(days=7)
            self.cursor.execute(query, (ticker, company_domain, cutoff))
            return self.cursor.fetchall() or []
        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []
    
    def _get_options_flow(self, ticker: str, company_domain: str) -> Dict:
        """Get latest options flow signals"""
        try:
            query = """
                SELECT * FROM system_uno.options_flow_signals
                WHERE ticker = %s AND company_domain = %s
                ORDER BY signal_timestamp DESC
                LIMIT 1
            """
            self.cursor.execute(query, (ticker, company_domain))
            return self.cursor.fetchone() or {}
        except Exception as e:
            logger.error(f"Failed to get options flow: {e}")
            return {}
    
    def _calculate_technical_score(self, indicators: Dict) -> Dict:
        """Calculate technical analysis score"""
        if not indicators:
            return {'bullish': 50, 'bearish': 50}
        
        bullish = 0
        bearish = 0
        
        # RSI
        if indicators.get('rsi_14', 50) > 70:
            bearish += 20
        elif indicators.get('rsi_14', 50) < 30:
            bullish += 20
        
        # MACD
        if indicators.get('macd_histogram', 0) > 0:
            bullish += 15
        else:
            bearish += 15
        
        # Moving averages
        close = indicators.get('close', 0)
        if close > indicators.get('sma_50', close):
            bullish += 10
        else:
            bearish += 10
            
        if close > indicators.get('sma_200', close):
            bullish += 10
        else:
            bearish += 10
        
        # Bollinger Bands
        if close > indicators.get('bollinger_upper', close):
            bullish += 10
        elif close < indicators.get('bollinger_lower', close):
            bearish += 10
        
        # Normalize to 0-100
        total = bullish + bearish
        if total > 0:
            bullish = (bullish / total) * 100
            bearish = (bearish / total) * 100
        else:
            bullish = bearish = 50
        
        return {'bullish': bullish, 'bearish': bearish}
    
    def _calculate_pattern_score(self, patterns: List[Dict]) -> Dict:
        """Calculate pattern-based score"""
        if not patterns:
            return {'bullish': 50, 'bearish': 50}
        
        bullish = 0
        bearish = 0
        
        for pattern in patterns[:3]:  # Consider top 3 patterns
            confidence = pattern.get('confidence_score', 0) / 100
            if pattern.get('is_bullish'):
                bullish += confidence * 33.33
            else:
                bearish += confidence * 33.33
        
        # Normalize
        if bullish + bearish == 0:
            return {'bullish': 50, 'bearish': 50}
        
        total = bullish + bearish
        return {
            'bullish': (bullish / total) * 100,
            'bearish': (bearish / total) * 100
        }
    
    def _calculate_event_score(self, events: List[Dict]) -> Dict:
        """Calculate event-based score"""
        if not events:
            return {'bullish': 50, 'bearish': 50}
        
        bullish = 0
        bearish = 0
        
        for event in events:
            impact = event.get('price_impact', 0)
            significance = event.get('significance_score', 0) / 100
            
            if impact > 0:
                bullish += significance * 50
            elif impact < 0:
                bearish += significance * 50
        
        # Normalize
        if bullish + bearish == 0:
            return {'bullish': 50, 'bearish': 50}
        
        total = bullish + bearish
        return {
            'bullish': min((bullish / total) * 100, 100),
            'bearish': min((bearish / total) * 100, 100)
        }
    
    def _calculate_options_score(self, options_flow: Dict) -> Dict:
        """Calculate options flow score"""
        if not options_flow:
            return {'bullish': 50, 'bearish': 50}
        
        sentiment = options_flow.get('flow_sentiment', 'neutral')
        
        if sentiment == 'bullish':
            return {'bullish': 70, 'bearish': 30}
        elif sentiment == 'bearish':
            return {'bullish': 30, 'bearish': 70}
        else:
            return {'bullish': 50, 'bearish': 50}
    
    def _determine_signal_direction(self, bullish_score: float, 
                                   bearish_score: float) -> SignalDirection:
        """Determine signal direction based on scores"""
        diff = bullish_score - bearish_score
        
        if diff > 40:
            return SignalDirection.STRONG_BUY
        elif diff > 20:
            return SignalDirection.BUY
        elif diff < -40:
            return SignalDirection.STRONG_SELL
        elif diff < -20:
            return SignalDirection.SELL
        else:
            return SignalDirection.HOLD
    
    def _store_composite_signal(self, signal: Dict):
        """Store composite signal in database"""
        try:
            query = """
                INSERT INTO system_uno.composite_market_signals (
                    company_domain, ticker, signal_timestamp,
                    has_technical_signal, has_pattern_signal,
                    has_options_signal, has_event_signal,
                    bullish_score, bearish_score, confidence_score,
                    signal_direction, signal_strength, time_horizon,
                    signal_components, market_context,
                    expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            expires_at = signal['timestamp'] + timedelta(hours=24)
            
            values = (
                signal['company_domain'], signal['ticker'], signal['timestamp'],
                True, bool(signal['components']['patterns']),
                bool(signal['components']['options']), bool(signal['components']['events']),
                signal['bullish_score'], signal['bearish_score'], signal['confidence_score'],
                signal['signal_direction'], 
                'strong' if signal['confidence_score'] > 30 else 'moderate',
                'short',  # Default to short-term
                json.dumps(signal['components']), json.dumps({}),
                expires_at
            )
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"Stored composite signal for {signal['ticker']}")
            
        except Exception as e:
            logger.error(f"Failed to store composite signal: {e}")
            self.conn.rollback()
    
    def close(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connections closed")