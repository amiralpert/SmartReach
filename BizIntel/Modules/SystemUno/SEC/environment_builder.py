"""
Industry Environment Builder for SEC Analysis
Aggregates risk mentions across companies to build industry environment model
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import pandas as pd
import numpy as np
from collections import defaultdict, Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnvironmentBuilder:
    """
    Builds industry-wide risk environment from individual company mentions
    Identifies consensus, emerging, and unique risks
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """Initialize environment builder"""
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self._connect_db()
        
        # Thresholds for risk categorization
        self.consensus_threshold = 0.6  # >60% companies mention
        self.emerging_threshold = 0.1   # 10-60% companies mention
        
        logger.info("EnvironmentBuilder initialized")
    
    def _connect_db(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def build_industry_environment(self, industry_category: str,
                                  time_period: str = None) -> Dict:
        """
        Build environment model for an industry
        
        Args:
            industry_category: Industry to analyze
            time_period: Period to analyze (e.g., 'Q1-2024')
            
        Returns:
            Environment analysis dictionary
        """
        logger.info(f"Building environment for {industry_category}")
        
        try:
            # Determine time period
            if not time_period:
                time_period = self._get_current_period()
            
            # Get all mentions for industry and period
            mentions = self._get_industry_mentions(industry_category, time_period)
            
            if not mentions:
                logger.warning(f"No mentions found for {industry_category} in {time_period}")
                return {
                    'industry_category': industry_category,
                    'time_period': time_period,
                    'status': 'no_data'
                }
            
            # Analyze mentions
            analysis = self._analyze_mentions(mentions, industry_category)
            
            # Build environment model
            environment = self._build_environment_model(analysis, industry_category, time_period)
            
            # Store in database
            self._store_environment(environment)
            
            return environment
            
        except Exception as e:
            logger.error(f"Failed to build environment for {industry_category}: {e}")
            return {
                'industry_category': industry_category,
                'time_period': time_period,
                'status': 'error',
                'error': str(e)
            }
    
    def _get_current_period(self) -> str:
        """Get current reporting period"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"Q{quarter}-{now.year}"
    
    def _get_industry_mentions(self, industry_category: str,
                               time_period: str) -> List[Dict]:
        """Get all risk mentions for industry and period"""
        try:
            # Parse time period
            period_start, period_end = self._parse_period(time_period)
            
            query = """
                SELECT 
                    m.*,
                    d.filing_date,
                    d.filing_type,
                    c.market_cap
                FROM systemuno_sec.environment_mentions m
                JOIN systemuno_sec.data_documents d ON m.document_id = d.id
                LEFT JOIN core.companies c ON m.company_domain = c.domain
                WHERE m.industry_category = %s
                AND d.filing_date BETWEEN %s AND %s
                ORDER BY d.filing_date DESC
            """
            
            self.cursor.execute(query, (industry_category, period_start, period_end))
            return self.cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Failed to get mentions: {e}")
            return []
    
    def _parse_period(self, time_period: str) -> Tuple[datetime, datetime]:
        """Parse time period string to date range"""
        if '-' in time_period:
            # Quarter format: Q1-2024
            quarter_str, year_str = time_period.split('-')
            year = int(year_str)
            quarter = int(quarter_str[1])
            
            # Calculate start and end dates
            start_month = (quarter - 1) * 3 + 1
            end_month = start_month + 2
            
            period_start = datetime(year, start_month, 1)
            
            # Get last day of end month
            if end_month == 12:
                period_end = datetime(year, 12, 31)
            else:
                period_end = datetime(year, end_month + 1, 1) - timedelta(days=1)
        else:
            # Assume fiscal year: FY-2024
            year = int(time_period.split('-')[1])
            period_start = datetime(year, 1, 1)
            period_end = datetime(year, 12, 31)
        
        return period_start, period_end
    
    def _analyze_mentions(self, mentions: List[Dict],
                         industry_category: str) -> Dict:
        """Analyze mentions to identify patterns"""
        analysis = {
            'total_companies': len(set(m['company_domain'] for m in mentions)),
            'total_mentions': len(mentions),
            'risk_themes': defaultdict(lambda: {
                'companies': set(),
                'total_mentions': 0,
                'avg_sentiment': 0,
                'sample_texts': []
            }),
            'company_coverage': defaultdict(set),
            'temporal_trends': defaultdict(list)
        }
        
        # Process each mention
        for mention in mentions:
            theme = mention['risk_theme']
            company = mention['company_domain']
            
            # Track theme statistics
            analysis['risk_themes'][theme]['companies'].add(company)
            analysis['risk_themes'][theme]['total_mentions'] += mention.get('mention_count', 1)
            
            # Collect sample texts
            if mention.get('mention_text') and len(analysis['risk_themes'][theme]['sample_texts']) < 5:
                analysis['risk_themes'][theme]['sample_texts'].append(mention['mention_text'])
            
            # Track sentiment
            if mention.get('sentiment') is not None:
                analysis['risk_themes'][theme]['avg_sentiment'] += mention['sentiment']
            
            # Track company coverage
            analysis['company_coverage'][company].add(theme)
            
            # Track temporal trends
            if mention.get('filing_date'):
                analysis['temporal_trends'][theme].append(mention['filing_date'])
        
        # Calculate averages
        for theme, data in analysis['risk_themes'].items():
            if data['total_mentions'] > 0:
                data['avg_sentiment'] /= data['total_mentions']
            data['companies'] = list(data['companies'])  # Convert set to list for JSON
        
        return analysis
    
    def _build_environment_model(self, analysis: Dict,
                                 industry_category: str,
                                 time_period: str) -> Dict:
        """Build environment model from analysis"""
        total_companies = analysis['total_companies']
        
        # Categorize risks
        consensus_risks = {}
        emerging_risks = {}
        unique_risks = {}
        
        for theme, data in analysis['risk_themes'].items():
            coverage_ratio = len(data['companies']) / total_companies if total_companies > 0 else 0
            
            risk_info = {
                'theme': theme,
                'company_count': len(data['companies']),
                'coverage_ratio': coverage_ratio,
                'total_mentions': data['total_mentions'],
                'avg_sentiment': data['avg_sentiment'],
                'sample_texts': data['sample_texts'][:3]  # Top 3 samples
            }
            
            if coverage_ratio > self.consensus_threshold:
                consensus_risks[theme] = risk_info
            elif coverage_ratio > self.emerging_threshold:
                emerging_risks[theme] = risk_info
            else:
                unique_risks[theme] = risk_info
        
        # Identify market themes
        market_themes = self._identify_market_themes(analysis['risk_themes'])
        regulatory_themes = self._identify_regulatory_themes(analysis['risk_themes'])
        technology_themes = self._identify_technology_themes(analysis['risk_themes'])
        
        # Calculate risk momentum
        risk_momentum = self._calculate_risk_momentum(analysis, industry_category, time_period)
        
        # Identify new and retired risks
        new_risks, retired_risks = self._identify_risk_changes(
            industry_category, time_period, list(analysis['risk_themes'].keys())
        )
        
        # Calculate statistical measures
        risk_dispersion = self._calculate_risk_dispersion(analysis)
        consensus_strength = self._calculate_consensus_strength(consensus_risks, total_companies)
        
        return {
            'industry_category': industry_category,
            'time_period': time_period,
            'consensus_risks': consensus_risks,
            'emerging_risks': emerging_risks,
            'unique_risks': unique_risks,
            'market_themes': market_themes,
            'regulatory_themes': regulatory_themes,
            'technology_themes': technology_themes,
            'total_companies': total_companies,
            'total_filings_analyzed': analysis['total_mentions'],
            'risk_momentum': risk_momentum,
            'new_risks_detected': new_risks,
            'retired_risks': retired_risks,
            'risk_dispersion': risk_dispersion,
            'consensus_strength': consensus_strength,
            'created_at': datetime.now()
        }
    
    def _identify_market_themes(self, risk_themes: Dict) -> List[str]:
        """Identify market-related themes"""
        market_keywords = ['competition', 'market', 'pricing', 'demand', 'supply']
        themes = []
        
        for theme, data in risk_themes.items():
            if any(keyword in theme.lower() for keyword in market_keywords):
                if data['total_mentions'] > 5:  # Significant mentions
                    themes.append(theme)
        
        return sorted(themes, key=lambda x: risk_themes[x]['total_mentions'], reverse=True)[:5]
    
    def _identify_regulatory_themes(self, risk_themes: Dict) -> List[str]:
        """Identify regulatory themes"""
        regulatory_keywords = ['regulation', 'fda', 'compliance', 'government', 'approval']
        themes = []
        
        for theme, data in risk_themes.items():
            if any(keyword in theme.lower() for keyword in regulatory_keywords):
                if data['total_mentions'] > 3:
                    themes.append(theme)
        
        return sorted(themes, key=lambda x: risk_themes[x]['total_mentions'], reverse=True)[:5]
    
    def _identify_technology_themes(self, risk_themes: Dict) -> List[str]:
        """Identify technology themes"""
        tech_keywords = ['technology', 'digital', 'cyber', 'ai', 'innovation', 'patent']
        themes = []
        
        for theme, data in risk_themes.items():
            if any(keyword in theme.lower() for keyword in tech_keywords):
                if data['total_mentions'] > 3:
                    themes.append(theme)
        
        return sorted(themes, key=lambda x: risk_themes[x]['total_mentions'], reverse=True)[:5]
    
    def _calculate_risk_momentum(self, analysis: Dict,
                                 industry_category: str,
                                 time_period: str) -> str:
        """Calculate overall risk momentum for industry"""
        try:
            # Get previous period
            previous_period = self._get_previous_period(time_period)
            
            # Get previous environment
            self.cursor.execute("""
                SELECT consensus_risks, emerging_risks
                FROM systemuno_sec.environment
                WHERE industry_category = %s
                AND time_period = %s
            """, (industry_category, previous_period))
            
            previous = self.cursor.fetchone()
            
            if not previous:
                return 'stable'  # No previous data
            
            # Compare risk counts
            current_risk_count = len(analysis['risk_themes'])
            previous_risk_count = len(previous.get('consensus_risks', {})) + \
                                len(previous.get('emerging_risks', {}))
            
            if current_risk_count > previous_risk_count * 1.2:
                return 'increasing'
            elif current_risk_count < previous_risk_count * 0.8:
                return 'decreasing'
            else:
                return 'stable'
                
        except Exception as e:
            logger.error(f"Failed to calculate momentum: {e}")
            return 'unknown'
    
    def _get_previous_period(self, time_period: str) -> str:
        """Get previous reporting period"""
        if 'Q' in time_period:
            quarter_str, year_str = time_period.split('-')
            quarter = int(quarter_str[1])
            year = int(year_str)
            
            if quarter == 1:
                return f"Q4-{year-1}"
            else:
                return f"Q{quarter-1}-{year}"
        else:
            # Fiscal year
            year = int(time_period.split('-')[1])
            return f"FY-{year-1}"
    
    def _identify_risk_changes(self, industry_category: str,
                               time_period: str,
                               current_risks: List[str]) -> Tuple[List[str], List[str]]:
        """Identify new and retired risks"""
        try:
            previous_period = self._get_previous_period(time_period)
            
            # Get previous risks
            self.cursor.execute("""
                SELECT consensus_risks, emerging_risks
                FROM systemuno_sec.environment
                WHERE industry_category = %s
                AND time_period = %s
            """, (industry_category, previous_period))
            
            previous = self.cursor.fetchone()
            
            if not previous:
                return current_risks[:5], []  # All risks are new
            
            previous_risks = set()
            if previous.get('consensus_risks'):
                previous_risks.update(previous['consensus_risks'].keys())
            if previous.get('emerging_risks'):
                previous_risks.update(previous['emerging_risks'].keys())
            
            current_risk_set = set(current_risks)
            
            new_risks = list(current_risk_set - previous_risks)
            retired_risks = list(previous_risks - current_risk_set)
            
            return new_risks[:5], retired_risks[:5]
            
        except Exception as e:
            logger.error(f"Failed to identify risk changes: {e}")
            return [], []
    
    def _calculate_risk_dispersion(self, analysis: Dict) -> float:
        """Calculate variance in risk mentions across companies"""
        if not analysis['company_coverage']:
            return 0.0
        
        # Count risks per company
        risk_counts = [len(risks) for risks in analysis['company_coverage'].values()]
        
        if not risk_counts:
            return 0.0
        
        # Calculate coefficient of variation
        mean_risks = np.mean(risk_counts)
        std_risks = np.std(risk_counts)
        
        if mean_risks == 0:
            return 0.0
        
        return std_risks / mean_risks
    
    def _calculate_consensus_strength(self, consensus_risks: Dict,
                                      total_companies: int) -> float:
        """Calculate how strongly companies agree on risks"""
        if not consensus_risks or total_companies == 0:
            return 0.0
        
        # Average coverage ratio for consensus risks
        coverage_ratios = [risk['coverage_ratio'] for risk in consensus_risks.values()]
        
        if not coverage_ratios:
            return 0.0
        
        return np.mean(coverage_ratios)
    
    def _store_environment(self, environment: Dict):
        """Store environment in database"""
        try:
            query = """
                INSERT INTO systemuno_sec.environment (
                    industry_category, time_period,
                    consensus_risks, emerging_risks, unique_risks,
                    market_themes, regulatory_themes, technology_themes,
                    total_companies, total_filings_analyzed,
                    risk_momentum, new_risks_detected, retired_risks,
                    risk_dispersion, consensus_strength
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (industry_category, time_period) DO UPDATE SET
                    consensus_risks = EXCLUDED.consensus_risks,
                    emerging_risks = EXCLUDED.emerging_risks,
                    unique_risks = EXCLUDED.unique_risks,
                    market_themes = EXCLUDED.market_themes,
                    regulatory_themes = EXCLUDED.regulatory_themes,
                    technology_themes = EXCLUDED.technology_themes,
                    total_companies = EXCLUDED.total_companies,
                    total_filings_analyzed = EXCLUDED.total_filings_analyzed,
                    risk_momentum = EXCLUDED.risk_momentum,
                    new_risks_detected = EXCLUDED.new_risks_detected,
                    retired_risks = EXCLUDED.retired_risks,
                    risk_dispersion = EXCLUDED.risk_dispersion,
                    consensus_strength = EXCLUDED.consensus_strength,
                    updated_at = NOW()
            """
            
            values = (
                environment['industry_category'],
                environment['time_period'],
                json.dumps(environment['consensus_risks']),
                json.dumps(environment['emerging_risks']),
                json.dumps(environment['unique_risks']),
                environment['market_themes'],
                environment['regulatory_themes'],
                environment['technology_themes'],
                environment['total_companies'],
                environment['total_filings_analyzed'],
                environment['risk_momentum'],
                environment['new_risks_detected'],
                environment['retired_risks'],
                environment['risk_dispersion'],
                environment['consensus_strength']
            )
            
            self.cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"Stored environment for {environment['industry_category']} - {environment['time_period']}")
            
        except Exception as e:
            logger.error(f"Failed to store environment: {e}")
            self.conn.rollback()
    
    def build_all_industries(self, time_period: str = None) -> Dict:
        """Build environment for all industries"""
        logger.info("Building environment for all industries")
        
        try:
            # Get all industry categories
            self.cursor.execute("""
                SELECT DISTINCT industry_category
                FROM systemuno_sec.data_documents
                WHERE industry_category IS NOT NULL
            """)
            
            industries = [row['industry_category'] for row in self.cursor.fetchall()]
            
            if not industries:
                return {'status': 'no_industries'}
            
            results = {}
            for industry in industries:
                logger.info(f"Processing {industry}")
                result = self.build_industry_environment(industry, time_period)
                results[industry] = result
            
            return {
                'status': 'success',
                'industries_processed': len(industries),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Failed to build all industries: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_cross_industry_insights(self, time_period: str = None) -> Dict:
        """Get insights across all industries"""
        if not time_period:
            time_period = self._get_current_period()
        
        try:
            # Get all environments for period
            self.cursor.execute("""
                SELECT *
                FROM systemuno_sec.environment
                WHERE time_period = %s
            """, (time_period,))
            
            environments = self.cursor.fetchall()
            
            if not environments:
                return {'status': 'no_data'}
            
            # Aggregate insights
            all_consensus_risks = Counter()
            all_emerging_risks = Counter()
            momentum_distribution = Counter()
            
            for env in environments:
                # Count consensus risks across industries
                if env.get('consensus_risks'):
                    for risk in env['consensus_risks'].keys():
                        all_consensus_risks[risk] += 1
                
                # Count emerging risks
                if env.get('emerging_risks'):
                    for risk in env['emerging_risks'].keys():
                        all_emerging_risks[risk] += 1
                
                # Track momentum
                momentum_distribution[env.get('risk_momentum', 'unknown')] += 1
            
            return {
                'time_period': time_period,
                'industries_analyzed': len(environments),
                'top_consensus_risks': all_consensus_risks.most_common(10),
                'top_emerging_risks': all_emerging_risks.most_common(10),
                'momentum_distribution': dict(momentum_distribution),
                'highest_dispersion': max(environments, key=lambda x: x.get('risk_dispersion', 0)),
                'strongest_consensus': max(environments, key=lambda x: x.get('consensus_strength', 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get cross-industry insights: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def close(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connections closed")


# Main execution
if __name__ == "__main__":
    # Database configuration
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    builder = EnvironmentBuilder(db_config)
    
    # Build environment for biotech industry
    result = builder.build_industry_environment('biotech_therapeutics')
    print(json.dumps(result, indent=2, default=str))
    
    # Get cross-industry insights
    insights = builder.get_cross_industry_insights()
    print("\nCross-Industry Insights:")
    print(json.dumps(insights, indent=2, default=str))
    
    builder.close()