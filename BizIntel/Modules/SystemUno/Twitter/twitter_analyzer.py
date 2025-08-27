"""
SystemUno Twitter Analyzer - Main Orchestrator
Coordinates all Twitter analysis modules for comprehensive social media intelligence
"""

import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Twitter.twitter_sentiment import TwitterSentimentAnalyzer
from Twitter.twitter_entities import TwitterEntityExtractor
from Twitter.twitter_network import TwitterNetworkAnalyzer
from Twitter.twitter_engagement import TwitterEngagementAnalyzer
from Twitter.twitter_kol import TwitterKOLIdentifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterAnalyzer:
    """
    Main Twitter analyzer that orchestrates all analysis modules
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize Twitter analyzer with all sub-modules
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config
        
        # Initialize sub-analyzers
        self.sentiment_analyzer = TwitterSentimentAnalyzer()
        self.entity_extractor = TwitterEntityExtractor()
        self.network_analyzer = TwitterNetworkAnalyzer(db_config)
        self.engagement_analyzer = TwitterEngagementAnalyzer(db_config)
        self.kol_identifier = TwitterKOLIdentifier(db_config)
        
        # Load parameters from systemuno_central
        self.parameters = self._load_parameters()
        
        logger.info("Twitter Analyzer initialized with all modules")
    
    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def _load_parameters(self) -> Dict:
        """Load parameters from systemuno_central"""
        params = {}
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT param_key, param_value, data_type
                FROM systemuno_central.parameter_definitions
                WHERE domain = 'twitter' AND is_active = true
            """)
            
            for row in cursor.fetchall():
                key = row['param_key'].replace('uno.twitter.', '')
                value = row['param_value']
                
                # Convert based on data type
                if row['data_type'] == 'integer':
                    value = int(value)
                elif row['data_type'] == 'float':
                    value = float(value)
                elif row['data_type'] == 'boolean':
                    value = value.lower() == 'true'
                elif row['data_type'] == 'json':
                    value = json.loads(value)
                
                params[key] = value
            
            cursor.close()
            conn.close()
            
            logger.info(f"Loaded {len(params)} parameters from systemuno_central")
            
        except Exception as e:
            logger.error(f"Error loading parameters: {e}")
        
        return params
    
    def analyze_company(self, 
                       company_domain: str,
                       include_mentions: bool = True,
                       days_back: int = 7) -> Dict:
        """
        Run complete Twitter analysis for a company
        
        Args:
            company_domain: Company domain
            include_mentions: Whether to analyze mentions
            days_back: Number of days to analyze
            
        Returns:
            Comprehensive analysis results
        """
        logger.info(f"Starting Twitter analysis for {company_domain}")
        
        analysis_results = {
            'company_domain': company_domain,
            'analysis_timestamp': datetime.now().isoformat(),
            'parameters_snapshot': self.parameters,
            'tweets_analyzed': 0,
            'mentions_analyzed': 0
        }
        
        try:
            # 1. Fetch Twitter data
            tweets = self._fetch_tweets(company_domain, days_back)
            mentions = []
            if include_mentions:
                mentions = self._fetch_mentions(company_domain, days_back)
            
            analysis_results['tweets_analyzed'] = len(tweets)
            analysis_results['mentions_analyzed'] = len(mentions)
            
            if not tweets and not mentions:
                logger.warning(f"No Twitter data found for {company_domain}")
                return analysis_results
            
            # 2. Sentiment Analysis
            logger.info("Running sentiment analysis...")
            sentiment_results = self._analyze_sentiment(tweets, mentions)
            analysis_results['sentiment'] = sentiment_results
            
            # 3. Entity Extraction
            logger.info("Extracting entities...")
            entity_results = self._extract_entities(tweets + mentions)
            analysis_results['entities'] = entity_results
            
            # 4. Network Analysis
            logger.info("Analyzing network...")
            network_results = self._analyze_network(tweets + mentions)
            analysis_results['network'] = network_results
            
            # 5. Engagement Analysis
            logger.info("Analyzing engagement...")
            engagement_results = self._analyze_engagement(tweets)
            analysis_results['engagement'] = engagement_results
            
            # 6. KOL Identification
            logger.info("Identifying KOLs...")
            kol_results = self._identify_kols(mentions)
            analysis_results['kols'] = kol_results
            
            # 7. Save results to database
            self._save_results(analysis_results)
            
            # 8. Generate insights
            analysis_results['insights'] = self._generate_insights(analysis_results)
            
            logger.info(f"Twitter analysis completed for {company_domain}")
            
        except Exception as e:
            logger.error(f"Error analyzing {company_domain}: {e}")
            analysis_results['error'] = str(e)
        
        return analysis_results
    
    def _fetch_tweets(self, company_domain: str, days_back: int) -> List[Dict]:
        """Fetch tweets from database"""
        tweets = []
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    tweet_id, text, author_handle, created_at,
                    retweet_count, reply_count, like_count, quote_count,
                    tweet_type, hashtags, user_mentions, urls, has_media,
                    in_reply_to_user_handle, raw_json
                FROM social.twitter_activity
                WHERE company_domain = %s
                AND created_at >= %s
                ORDER BY created_at DESC
            """, (company_domain, datetime.now() - timedelta(days=days_back)))
            
            tweets = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
        
        return tweets
    
    def _fetch_mentions(self, company_domain: str, days_back: int) -> List[Dict]:
        """Fetch mentions from database"""
        mentions = []
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    tweet_id, text, author_username, author_verified,
                    created_at, mention_type, engagement_score,
                    retweet_count, like_count, reply_count, quote_count,
                    raw_data
                FROM social.twitter_mentions
                WHERE company_domain = %s
                AND created_at >= %s
                ORDER BY engagement_score DESC
            """, (company_domain, datetime.now() - timedelta(days=days_back)))
            
            mentions = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error fetching mentions: {e}")
        
        return mentions
    
    def _analyze_sentiment(self, tweets: List[Dict], mentions: List[Dict]) -> Dict:
        """Run sentiment analysis on tweets and mentions"""
        results = {
            'company_tweets': {},
            'mentions': {},
            'overall': {}
        }
        
        # Analyze company tweets
        if tweets:
            tweet_sentiments = []
            for tweet in tweets:
                sentiment = self.sentiment_analyzer.analyze_sentiment(tweet['text'])
                tweet_sentiments.append(sentiment)
            
            # Aggregate results
            results['company_tweets'] = self.sentiment_analyzer.aggregate_sentiment(tweet_sentiments)
            
            # Analyze thread sentiment if applicable
            thread_tweets = [t for t in tweets if t.get('in_reply_to_user_handle')]
            if thread_tweets:
                thread_result = self.sentiment_analyzer.analyze_thread(
                    [{'text': t['text'], 'created_at': t['created_at']} for t in thread_tweets]
                )
                results['company_tweets']['thread_analysis'] = thread_result
        
        # Analyze mentions
        if mentions:
            mention_sentiments = []
            for mention in mentions:
                sentiment = self.sentiment_analyzer.analyze_sentiment(mention['text'])
                mention_sentiments.append(sentiment)
            
            results['mentions'] = self.sentiment_analyzer.aggregate_sentiment(mention_sentiments)
        
        # Calculate overall sentiment
        all_sentiments = []
        if 'company_tweets' in results and 'sentiments' in results['company_tweets']:
            all_sentiments.extend(results['company_tweets']['sentiments'])
        if 'mentions' in results and 'sentiments' in results['mentions']:
            all_sentiments.extend(results['mentions']['sentiments'])
        
        if all_sentiments:
            results['overall'] = self.sentiment_analyzer.aggregate_sentiment(all_sentiments)
        
        return results
    
    def _extract_entities(self, tweets: List[Dict]) -> Dict:
        """Extract entities from tweets"""
        all_entities = []
        
        for tweet in tweets:
            text = tweet.get('text', '')
            if text:
                entities = self.entity_extractor.extract_entities(text)
                all_entities.append(entities)
        
        # Generate summary
        summary = self.entity_extractor.get_entity_summary(all_entities)
        
        # Extract key topics
        key_topics = set()
        for entities in all_entities:
            topics = self.entity_extractor.extract_key_topics(entities)
            key_topics.update(topics)
        
        return {
            'summary': summary,
            'key_topics': list(key_topics),
            'top_entities': summary.get('top_entities', {})
        }
    
    def _analyze_network(self, interactions: List[Dict]) -> Dict:
        """Analyze Twitter network"""
        # Build network from interactions
        network_data = []
        for interaction in interactions:
            network_item = {
                'author_username': interaction.get('author_handle') or interaction.get('author_username'),
                'mentioned_users': [],
                'in_reply_to_user': interaction.get('in_reply_to_user_handle')
            }
            
            # Add mentions
            if interaction.get('user_mentions'):
                network_item['mentioned_users'] = [
                    {'username': m} for m in interaction['user_mentions']
                ]
            
            network_data.append(network_item)
        
        # Build and analyze network
        graph = self.network_analyzer.build_network(network_data)
        
        if graph.number_of_nodes() == 0:
            return {'error': 'No network data available'}
        
        # Calculate metrics
        metrics = self.network_analyzer.calculate_centrality_metrics(graph)
        
        # Identify influencers
        influencers = self.network_analyzer.identify_influencers(metrics)
        
        # Detect communities
        communities = self.network_analyzer.detect_communities(graph)
        
        # Get network stats
        stats = self.network_analyzer.calculate_network_stats()
        
        return {
            'network_stats': stats,
            'top_influencers': influencers[:10],
            'communities_detected': len(set(communities.values())) if communities else 0,
            'key_nodes': len([n for n in graph.nodes() if graph.degree(n) > 5])
        }
    
    def _analyze_engagement(self, tweets: List[Dict]) -> Dict:
        """Analyze engagement patterns"""
        # Detect viral content
        viral = self.engagement_analyzer.detect_viral_content(tweets)
        
        # Analyze optimal timing
        timing = self.engagement_analyzer.analyze_optimal_timing(tweets)
        
        # Analyze content types
        content = self.engagement_analyzer.analyze_content_types(tweets)
        
        # Calculate average engagement rate
        engagement_rates = []
        for tweet in tweets:
            tweet['author_followers'] = 10000  # Default if not available
            rate = self.engagement_analyzer.calculate_engagement_rate(tweet)
            engagement_rates.append(rate)
        
        avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0
        
        return {
            'average_engagement_rate': round(avg_engagement, 2),
            'viral_content': viral[:5] if viral else [],
            'optimal_timing': timing.get('recommendations', []),
            'best_content_type': content.get('best_performing'),
            'content_recommendations': content.get('recommendations', [])
        }
    
    def _identify_kols(self, mentions: List[Dict]) -> Dict:
        """Identify KOLs from mentions"""
        # Get unique users who mentioned the company
        users = {}
        for mention in mentions:
            username = mention.get('author_username')
            if username and username not in users:
                users[username] = {
                    'username': username,
                    'verified': mention.get('author_verified', False),
                    'followers_count': 10000,  # Would need to fetch from profiles
                    'recent_tweets': [mention]
                }
            elif username:
                users[username]['recent_tweets'].append(mention)
        
        # Identify KOLs
        user_list = list(users.values())
        kols = self.kol_identifier.identify_kols(user_list, min_influence=50)
        
        # Generate report
        report = self.kol_identifier.generate_kol_report(kols)
        
        return {
            'identified_kols': len(kols),
            'top_kols': kols[:5] if kols else [],
            'report': report
        }
    
    def _save_results(self, results: Dict) -> None:
        """Save analysis results to database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            company_domain = results['company_domain']
            
            # Save sentiment analysis
            if 'sentiment' in results and 'overall' in results['sentiment']:
                sentiment = results['sentiment']['overall']
                cursor.execute("""
                    INSERT INTO systemuno_twitter.sentiment_analysis
                    (company_domain, tweet_id, sentiment_label, sentiment_score,
                     positive_score, negative_score, neutral_score, confidence,
                     analyzed_at, parameters_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    company_domain,
                    'aggregate_' + datetime.now().strftime('%Y%m%d'),
                    sentiment.get('dominant_sentiment', 'neutral'),
                    sentiment.get('average_score', 0),
                    sentiment.get('positive_ratio', 0),
                    sentiment.get('negative_ratio', 0),
                    sentiment.get('neutral_ratio', 0),
                    sentiment.get('average_confidence', 0),
                    datetime.now(),
                    json.dumps(results['parameters_snapshot'])
                ))
            
            # Save entity extractions
            if 'entities' in results:
                entities = results['entities']
                cursor.execute("""
                    INSERT INTO systemuno_twitter.entities
                    (company_domain, tweet_id, entity_type, entity_text,
                     confidence, start_pos, end_pos, extracted_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    company_domain,
                    'aggregate_' + datetime.now().strftime('%Y%m%d'),
                    'summary',
                    json.dumps(entities.get('top_entities', {})),
                    0.9,
                    0,
                    0,
                    datetime.now()
                ))
            
            # Save engagement analysis
            if 'engagement' in results:
                engagement = results['engagement']
                cursor.execute("""
                    INSERT INTO systemuno_twitter.engagement_analysis
                    (company_domain, tweet_id, engagement_rate, virality_score,
                     optimal_time, content_type, analyzed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    company_domain,
                    'aggregate_' + datetime.now().strftime('%Y%m%d'),
                    engagement.get('average_engagement_rate', 0),
                    len(engagement.get('viral_content', [])),
                    json.dumps(engagement.get('optimal_timing', [])),
                    engagement.get('best_content_type'),
                    datetime.now()
                ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Results saved to database")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def _generate_insights(self, results: Dict) -> List[str]:
        """Generate actionable insights from analysis"""
        insights = []
        
        # Sentiment insights
        if 'sentiment' in results and 'overall' in results['sentiment']:
            sentiment = results['sentiment']['overall']
            if sentiment.get('dominant_sentiment') == 'positive':
                insights.append(f"Positive sentiment dominates ({sentiment.get('positive_ratio', 0):.0%})")
            elif sentiment.get('dominant_sentiment') == 'negative':
                insights.append(f"⚠️ Negative sentiment detected ({sentiment.get('negative_ratio', 0):.0%})")
        
        # Engagement insights
        if 'engagement' in results:
            engagement = results['engagement']
            if engagement.get('viral_content'):
                insights.append(f"🚀 {len(engagement['viral_content'])} viral tweets detected")
            if engagement.get('average_engagement_rate', 0) > 5:
                insights.append("High engagement rate indicates strong audience connection")
        
        # KOL insights
        if 'kols' in results:
            kol_count = results['kols'].get('identified_kols', 0)
            if kol_count > 0:
                insights.append(f"📢 {kol_count} key opinion leaders identified")
        
        # Entity insights
        if 'entities' in results:
            topics = results['entities'].get('key_topics', [])
            if 'clinical_trials' in topics:
                insights.append("Clinical trial discussions detected")
            if 'regulatory' in topics:
                insights.append("Regulatory (FDA) mentions found")
        
        # Network insights
        if 'network' in results:
            network = results['network']
            if network.get('communities_detected', 0) > 3:
                insights.append(f"Multiple communities ({network['communities_detected']}) engaging with content")
        
        return insights


# Example usage
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load environment variables
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
    load_dotenv(env_path)
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Get company domain from command line or use default
    company_domain = sys.argv[1] if len(sys.argv) > 1 else "grail.com"
    
    # Initialize analyzer
    analyzer = TwitterAnalyzer(db_config)
    
    # Run analysis
    print(f"\nAnalyzing Twitter data for {company_domain}")
    print("="*60)
    
    results = analyzer.analyze_company(
        company_domain=company_domain,
        include_mentions=True,
        days_back=30
    )
    
    # Display results
    print(f"\nTweets analyzed: {results['tweets_analyzed']}")
    print(f"Mentions analyzed: {results['mentions_analyzed']}")
    
    if 'sentiment' in results:
        print("\nSentiment Analysis:")
        overall = results['sentiment'].get('overall', {})
        print(f"  Dominant: {overall.get('dominant_sentiment', 'N/A')}")
        print(f"  Positive: {overall.get('positive_ratio', 0):.0%}")
        print(f"  Negative: {overall.get('negative_ratio', 0):.0%}")
    
    if 'engagement' in results:
        print("\nEngagement Analysis:")
        engagement = results['engagement']
        print(f"  Average Rate: {engagement.get('average_engagement_rate', 0):.2f}%")
        print(f"  Viral Content: {len(engagement.get('viral_content', []))} tweets")
        print(f"  Best Content: {engagement.get('best_content_type', 'N/A')}")
    
    if 'kols' in results:
        print("\nKOL Analysis:")
        kols = results['kols']
        print(f"  Identified: {kols.get('identified_kols', 0)} KOLs")
        if kols.get('top_kols'):
            print("  Top KOLs:")
            for kol in kols['top_kols'][:3]:
                print(f"    - @{kol['username']} (Score: {kol.get('influence_score', 0):.1f})")
    
    if 'insights' in results:
        print("\nKey Insights:")
        for insight in results['insights']:
            print(f"  • {insight}")
    
    print("\n" + "="*60)
    print("Analysis complete!")