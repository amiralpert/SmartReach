# System 1 Market Analyzer

## Overview

The Market Analyzer is an advanced technical analysis engine that processes market data to generate actionable trading signals. It combines traditional technical indicators with pattern recognition and event detection to provide institutional-grade market analysis running entirely on local infrastructure.

Part of the SmartReach BizIntel System 1 (fast, domain-specific analysis) layer, this analyzer operates in real-time to identify trading opportunities, assess risk, and generate composite signals.

## Features

### 📊 Technical Indicators (29 total)
- **Moving Averages**: SMA (20/50/200), EMA (12/26)
- **Momentum**: RSI(14), MACD, Stochastic
- **Volatility**: Bollinger Bands, ATR(14)
- **Volume**: OBV, VWAP, Volume Ratio
- **Support/Resistance**: Pivot Points with S1/S2, R1/R2

### 🎯 Pattern Detection
- **Breakout Patterns**: Price escaping Bollinger Bands or support/resistance
- **Squeeze Patterns**: Bollinger Band compression indicating imminent volatility
- **Divergence Patterns**: Price/indicator disagreements signaling reversals

### ⚡ Event Detection
- **Volatility Spikes**: ATR percentile-based detection
- **Volume Surges**: Unusual trading activity (>3x average)
- **Trend Changes**: Golden Cross, Death Cross detection

### 🔄 Composite Signals
- Weighted scoring across all components
- 5-level signals: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
- Confidence scoring (0-100%)
- Risk/reward calculations

## Installation

### Prerequisites
```bash
# Python 3.13+
python --version

# PostgreSQL with SmartReach BizIntel database
psql -d smartreachbizintel -c "SELECT version();"
```

### Dependencies
```bash
pip install ta-lib psycopg2 pandas numpy
```

### Database Setup
```bash
# Run the migration to create required tables
psql -d smartreachbizintel -f /Database/migrations/create_market_analysis_schema.sql
```

## Usage

### Basic Example
```python
from market_analyzer import MarketAnalyzer

# Configure database connection
db_config = {
    'host': 'localhost',
    'database': 'smartreachbizintel',
    'user': 'srbiuser',
    'password': 'SRBI_dev_2025'
}

# Initialize analyzer
analyzer = MarketAnalyzer(db_config)

# Analyze a stock
ticker = 'AAPL'
company_domain = 'apple.com'

# Calculate technical indicators
indicators = analyzer.calculate_technical_indicators(ticker, company_domain, lookback_days=100)

# Detect patterns
patterns = analyzer.detect_patterns(ticker, company_domain)

# Detect events
events = analyzer.detect_events(ticker, company_domain)

# Generate composite signal
signal = analyzer.generate_composite_signal(ticker, company_domain)

print(f"Signal: {signal['signal_direction']}")
print(f"Confidence: {signal['confidence_score']:.1f}%")
```

### Batch Analysis
```python
# Analyze multiple stocks
tickers = [
    ('apple.com', 'AAPL'),
    ('microsoft.com', 'MSFT'),
    ('amazon.com', 'AMZN')
]

signals = []
for company_domain, ticker in tickers:
    signal = analyzer.generate_composite_signal(ticker, company_domain)
    signals.append(signal)

# Sort by confidence
signals.sort(key=lambda x: x['confidence_score'], reverse=True)

# Display top opportunities
for signal in signals[:3]:
    print(f"{signal['ticker']}: {signal['signal_direction']} ({signal['confidence_score']:.1f}%)")
```

## Configuration

### Parameter Customization
Parameters are stored in the `systemuno_market.analysis_parameters` table:

```sql
-- View current parameters
SELECT * FROM systemuno_market.analysis_parameters WHERE is_active = true;

-- Update RSI period
UPDATE systemuno_market.analysis_parameters 
SET technical_params = jsonb_set(technical_params, '{rsi_period}', '21')
WHERE parameter_set_name = 'default';
```

### Default Parameters
```json
{
  "technical": {
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bollinger_period": 20,
    "bollinger_std": 2,
    "atr_period": 14
  },
  "pattern": {
    "min_pattern_bars": 5,
    "breakout_volume_multiplier": 1.5,
    "min_confidence_score": 60
  },
  "composite": {
    "technical_weight": 0.3,
    "pattern_weight": 0.25,
    "options_weight": 0.3,
    "event_weight": 0.15
  }
}
```

## API Reference

### MarketAnalyzer Class

#### `__init__(db_config: Dict[str, str])`
Initialize the analyzer with database configuration.

#### `calculate_technical_indicators(ticker: str, company_domain: str, lookback_days: int = 100)`
Calculate and store technical indicators.

**Returns**: List[TechnicalIndicators]

#### `detect_patterns(ticker: str, company_domain: str)`
Detect technical patterns in price data.

**Returns**: List[Pattern]

#### `detect_events(ticker: str, company_domain: str)`
Detect market events and regime changes.

**Returns**: List[MarketEvent]

#### `generate_composite_signal(ticker: str, company_domain: str)`
Generate weighted composite trading signal.

**Returns**: Dict with signal direction, scores, and confidence

## Database Schema

### Tables Created
| Table | Purpose |
|-------|---------|
| `systemuno_market.technical_indicators` | Stores calculated indicators |
| `systemuno_market.patterns` | Detected patterns with targets |
| `systemuno_market.events` | Market events and regime changes |
| `system_uno.options_flow_signals` | Options activity analysis |
| `system_uno.composite_market_signals` | Combined trading signals |
| `systemuno_market.analysis_parameters` | Configuration parameters |

### Key Indexes
- `idx_technical_indicators_company_time` - Fast lookups by company/time
- `idx_patterns_active` - Active pattern filtering
- `idx_composite_signals_expires` - Signal expiration tracking

## Output Examples

### Technical Indicators
```python
{
    'ticker': 'AAPL',
    'timestamp': '2025-08-18 16:00:00',
    'rsi_14': 65.5,
    'macd_line': 2.34,
    'macd_signal': 1.98,
    'bollinger_upper': 155.20,
    'bollinger_lower': 145.80,
    'volume_ratio': 1.8
}
```

### Pattern Detection
```python
{
    'pattern_type': 'breakout',
    'pattern_name': 'Bollinger Band Upper Breakout',
    'confidence_score': 75.0,
    'entry_price': 151.50,
    'target_price': 159.00,
    'stop_loss': 148.00,
    'risk_reward_ratio': 2.14,
    'is_bullish': True
}
```

### Composite Signal
```python
{
    'ticker': 'AAPL',
    'signal_direction': 'buy',
    'bullish_score': 68.5,
    'bearish_score': 31.5,
    'confidence_score': 37.0,
    'components': {
        'technical': {'bullish': 70, 'bearish': 30},
        'patterns': {'bullish': 75, 'bearish': 25},
        'events': {'bullish': 50, 'bearish': 50},
        'options': {'bullish': 70, 'bearish': 30}
    }
}
```

## Integration

### Data Flow
```
Market Data (Week 2)
    ↓
Market Analyzer (Week 3)
    ↓
Database Storage (system_uno schema)
    ↓
System 2 Meta-Analysis (Future)
```

### Master Orchestration
```python
# In master_orchestration.py
from SystemUno.MarketData.market_analyzer import MarketAnalyzer

async def analyze_market_data(ticker, company_domain):
    analyzer = MarketAnalyzer(db_config)
    
    # Run analysis
    indicators = analyzer.calculate_technical_indicators(ticker, company_domain)
    patterns = analyzer.detect_patterns(ticker, company_domain)
    signal = analyzer.generate_composite_signal(ticker, company_domain)
    
    return signal
```

## Performance

### Metrics
- **Indicator Calculation**: ~50ms for 100 days of data
- **Pattern Detection**: ~20ms per ticker
- **Event Detection**: ~15ms per ticker
- **Composite Signal**: ~10ms generation
- **Database Writes**: Batch optimized with ON CONFLICT

### Optimization Tips
1. **Use batch processing** for multiple tickers
2. **Limit lookback period** to necessary timeframe
3. **Create custom indexes** for frequent queries
4. **Use connection pooling** for high-volume analysis
5. **Cache parameters** to reduce database calls

## Error Handling

The analyzer includes comprehensive error handling:
- Transaction rollback on failures
- Graceful degradation when data is insufficient
- Detailed logging for debugging
- Default parameters as fallback

## Testing

Run the test suite:
```bash
python test_market_analyzer.py
```

Tests verify:
- Technical indicator accuracy
- Pattern detection sensitivity
- Event detection thresholds
- Composite signal generation
- Database operations

## Troubleshooting

### Common Issues

**Insufficient Data**
```python
# Requires minimum 30 days of data for indicators
# Check available data:
SELECT COUNT(*) FROM market.market_data 
WHERE ticker = 'AAPL' AND time >= NOW() - INTERVAL '30 days';
```

**TA-Lib Installation**
```bash
# macOS with Homebrew
brew install ta-lib
pip install ta-lib

# Linux
sudo apt-get install ta-lib
pip install ta-lib
```

**Database Connection**
```python
# Test connection
psql -h localhost -U srbiuser -d smartreachbizintel -c "SELECT 1;"
```

## Future Enhancements

- [ ] Real-time streaming analysis
- [ ] Machine learning pattern recognition
- [ ] Backtesting framework
- [ ] Custom indicator plugins
- [ ] WebSocket notifications
- [ ] Multi-timeframe analysis

## Contributing

When adding new features:
1. Add indicators to `TechnicalIndicators` dataclass
2. Update database schema migration
3. Implement calculation in `_calculate_all_indicators`
4. Add tests in `test_market_analyzer.py`
5. Update this README

## License

Proprietary - SmartReach BizIntel

## Support

For issues or questions:
- Check logs in application output
- Review test cases for examples
- Consult database schema documentation

---

*Last Updated: August 2025*
*Version: 1.0.0*