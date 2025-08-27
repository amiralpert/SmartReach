"""
Twitter KOL (Key Opinion Leader) Identification Module for SystemUno
Identifies and analyzes influential users in specific domains
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterKOLIdentifier:
    """
    Identifies and analyzes Key Opinion Leaders on Twitter
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize KOL identifier
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config
        
        # KOL identification parameters
        self.min_followers = 5000
        self.min_engagement_rate = 2.0  # 2% minimum
        self.influence_threshold = 80.0  # Score threshold for KOL status
        
        # Domain expertise keywords
        self.expertise_keywords = {
            'biotech': [
                'biotech', 'pharma', 'drug', 'FDA', 'clinical', 'trial',
                'therapy', 'treatment', 'oncology', 'genomics', 'vaccine',
                'antibody', 'molecule', 'compound', 'biologic'
            ],
            'finance': [
                'invest', 'stock', 'market', 'trading', 'IPO', 'valuation',
                'earnings', 'revenue', 'portfolio', 'equity', 'capital',
                'merger', 'acquisition', 'analyst', 'bullish', 'bearish'
            ],
            'healthcare': [
                'health', 'medical', 'patient', 'doctor', 'hospital',
                'diagnosis', 'disease', 'medicine', 'healthcare', 'clinical'
            ],
            'technology': [
                'AI', 'ML', 'tech', 'software', 'data', 'digital',
                'innovation', 'startup', 'platform', 'algorithm'
            ]
        }
    
    def calculate_influence_score(self, user_data: Dict) -> float:
        """
        Calculate composite influence score for a user
        
        Args:
            user_data: User metrics and activity data
            
        Returns:
            Influence score (0-100)
        """
        score_components = {}
        
        # 1. Reach Score (30% weight) - Based on followers
        followers = user_data.get('followers_count', 0)
        reach_score = min(np.log10(max(followers, 1)) / 6 * 100, 100)  # log scale, max at 1M followers
        score_components['reach'] = reach_score * 0.30
        
        # 2. Engagement Score (25% weight) - Based on engagement rate
        engagement_rate = self._calculate_engagement_rate(user_data)
        engagement_score = min(engagement_rate * 10, 100)  # 10% engagement = 100 score
        score_components['engagement'] = engagement_score * 0.25
        
        # 3. Authority Score (20% weight) - Based on verified status and profile completeness
        authority_score = 0
        if user_data.get('verified'):
            authority_score += 50
        if user_data.get('bio'):
            authority_score += 25
        if user_data.get('location'):
            authority_score += 15
        if user_data.get('website'):
            authority_score += 10
        score_components['authority'] = authority_score * 0.20
        
        # 4. Activity Score (15% weight) - Based on posting frequency
        tweets_count = user_data.get('tweets_count', 0)
        days_active = max((datetime.now() - user_data.get('created_at', datetime.now())).days, 1)
        tweets_per_day = tweets_count / days_active
        activity_score = min(tweets_per_day * 20, 100)  # 5 tweets/day = 100 score
        score_components['activity'] = activity_score * 0.15
        
        # 5. Network Score (10% weight) - Based on follower/following ratio
        following = user_data.get('following_count', 1)
        follower_ratio = followers / max(following, 1)
        network_score = min(follower_ratio * 10, 100)  # 10:1 ratio = 100 score
        score_components['network'] = network_score * 0.10
        
        # Calculate total score
        total_score = sum(score_components.values())
        
        return round(total_score, 2)
    
    def _calculate_engagement_rate(self, user_data: Dict) -> float:
        """
        Calculate average engagement rate for user's tweets
        
        Args:
            user_data: User data including recent tweets
            
        Returns:
            Engagement rate percentage
        """
        recent_tweets = user_data.get('recent_tweets', [])
        if not recent_tweets:
            return 0.0
        
        total_rate = 0
        valid_tweets = 0
        
        for tweet in recent_tweets:
            engagements = (
                tweet.get('like_count', 0) +
                tweet.get('retweet_count', 0) +
                tweet.get('reply_count', 0)
            )
            
            # Estimate impressions from followers
            impressions = user_data.get('followers_count', 1000) * 0.1
            
            if impressions > 0:
                rate = (engagements / impressions) * 100
                total_rate += rate
                valid_tweets += 1
        
        if valid_tweets > 0:
            return total_rate / valid_tweets
        
        return 0.0
    
    def classify_expertise(self, user_data: Dict) -> Dict[str, float]:
        """
        Classify user's domain expertise based on content
        
        Args:
            user_data: User data including bio and tweets
            
        Returns:
            Dictionary of domain scores
        """
        expertise_scores = defaultdict(float)
        
        # Analyze bio
        bio = (user_data.get('bio', '') or '').lower()
        for domain, keywords in self.expertise_keywords.items():
            for keyword in keywords:
                if keyword.lower() in bio:
                    expertise_scores[domain] += 2.0  # Bio mentions worth more
        
        # Analyze recent tweets
        recent_tweets = user_data.get('recent_tweets', [])
        for tweet in recent_tweets:
            text = (tweet.get('text', '') or '').lower()
            for domain, keywords in self.expertise_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in text:
                        expertise_scores[domain] += 1.0
        
        # Normalize scores
        total = sum(expertise_scores.values())
        if total > 0:
            for domain in expertise_scores:
                expertise_scores[domain] = (expertise_scores[domain] / total) * 100
        
        return dict(expertise_scores)
    
    def identify_kols(self, 
                     users: List[Dict],
                     domain_filter: Optional[str] = None,
                     min_influence: Optional[float] = None) -> List[Dict]:
        """
        Identify KOLs from a list of users
        
        Args:
            users: List of user data
            domain_filter: Optional domain to filter by
            min_influence: Minimum influence score (default: self.influence_threshold)
            
        Returns:
            List of identified KOLs with analysis
        """
        if min_influence is None:
            min_influence = self.influence_threshold
        
        kols = []
        
        for user in users:
            # Check minimum followers
            if user.get('followers_count', 0) < self.min_followers:
                continue
            
            # Calculate influence score
            influence_score = self.calculate_influence_score(user)
            
            if influence_score < min_influence:
                continue
            
            # Classify expertise
            expertise = self.classify_expertise(user)
            
            # Apply domain filter if specified
            if domain_filter and expertise.get(domain_filter, 0) < 20:
                continue
            
            # Determine primary domain
            primary_domain = max(expertise.items(), key=lambda x: x[1])[0] if expertise else 'general'
            
            kol_profile = {
                'username': user.get('username'),
                'name': user.get('name'),
                'influence_score': influence_score,
                'followers_count': user.get('followers_count'),
                'verified': user.get('verified', False),
                'primary_domain': primary_domain,
                'expertise_scores': expertise,
                'engagement_rate': self._calculate_engagement_rate(user),
                'bio': user.get('bio'),
                'location': user.get('location'),
                'metrics': {
                    'tweets_count': user.get('tweets_count'),
                    'following_count': user.get('following_count'),
                    'listed_count': user.get('listed_count')
                }
            }
            
            kols.append(kol_profile)
        
        # Sort by influence score
        kols.sort(key=lambda x: x['influence_score'], reverse=True)
        
        return kols
    
    def analyze_kol_sentiment(self, 
                             kol_username: str,
                             tweets: List[Dict],
                             company_keywords: List[str]) -> Dict:
        """
        Analyze a KOL's sentiment towards specific companies/topics
        
        Args:
            kol_username: KOL's username
            tweets: KOL's tweets
            company_keywords: Keywords to track sentiment for
            
        Returns:
            Sentiment analysis for the KOL
        """
        relevant_tweets = []
        sentiments = []
        
        for tweet in tweets:
            text = tweet.get('text', '').lower()
            
            # Check if tweet mentions company/topic
            is_relevant = any(keyword.lower() in text for keyword in company_keywords)
            
            if is_relevant:
                relevant_tweets.append(tweet)
                
                # Get sentiment if available
                if 'sentiment' in tweet:
                    sentiments.append(tweet['sentiment'])
        
        if not relevant_tweets:
            return {
                'kol_username': kol_username,
                'relevant_tweets': 0,
                'sentiment': 'neutral',
                'sentiment_score': 0.0
            }
        
        # Calculate average sentiment
        if sentiments:
            sentiment_values = {
                'positive': 1,
                'neutral': 0,
                'negative': -1
            }
            
            scores = [sentiment_values.get(s, 0) for s in sentiments]
            avg_score = np.mean(scores)
            
            if avg_score > 0.3:
                overall_sentiment = 'positive'
            elif avg_score < -0.3:
                overall_sentiment = 'negative'
            else:
                overall_sentiment = 'neutral'
        else:
            overall_sentiment = 'neutral'
            avg_score = 0.0
        
        return {
            'kol_username': kol_username,
            'relevant_tweets': len(relevant_tweets),
            'sentiment': overall_sentiment,
            'sentiment_score': round(avg_score, 3),
            'sample_tweets': relevant_tweets[:3]  # Include sample tweets
        }
    
    def track_kol_network(self, 
                         kol_username: str,
                         interactions: List[Dict]) -> Dict:
        """
        Track a KOL's network and interactions
        
        Args:
            kol_username: KOL's username
            interactions: List of interactions (mentions, replies, retweets)
            
        Returns:
            Network analysis for the KOL
        """
        network = {
            'frequently_mentions': defaultdict(int),
            'frequently_replied_to': defaultdict(int),
            'frequently_retweeted': defaultdict(int),
            'mutual_interactions': set()
        }
        
        for interaction in interactions:
            author = interaction.get('author_username')
            
            # Track mentions
            if 'user_mentions' in interaction:
                for mention in interaction['user_mentions']:
                    if mention != kol_username:
                        network['frequently_mentions'][mention] += 1
            
            # Track replies
            if interaction.get('in_reply_to_user'):
                reply_to = interaction['in_reply_to_user']
                if reply_to != kol_username:
                    network['frequently_replied_to'][reply_to] += 1
            
            # Track retweets
            if interaction.get('retweeted_user'):
                rt_user = interaction['retweeted_user']
                if rt_user != kol_username:
                    network['frequently_retweeted'][rt_user] += 1
        
        # Find mutual interactions (users who interact back)
        all_interactions = set()
        all_interactions.update(network['frequently_mentions'].keys())
        all_interactions.update(network['frequently_replied_to'].keys())
        all_interactions.update(network['frequently_retweeted'].keys())
        
        # Convert to sorted lists
        analysis = {
            'kol_username': kol_username,
            'top_mentions': sorted(network['frequently_mentions'].items(), 
                                 key=lambda x: x[1], reverse=True)[:10],
            'top_replies': sorted(network['frequently_replied_to'].items(), 
                                key=lambda x: x[1], reverse=True)[:10],
            'top_retweets': sorted(network['frequently_retweeted'].items(), 
                                 key=lambda x: x[1], reverse=True)[:10],
            'unique_interactions': len(all_interactions),
            'total_interactions': len(interactions)
        }
        
        return analysis
    
    def identify_rising_influencers(self, 
                                   users: List[Dict],
                                   lookback_days: int = 30) -> List[Dict]:
        """
        Identify rising influencers based on growth metrics
        
        Args:
            users: List of user data with historical metrics
            lookback_days: Days to look back for growth calculation
            
        Returns:
            List of rising influencers
        """
        rising_influencers = []
        
        for user in users:
            # Need historical data to calculate growth
            if not user.get('historical_metrics'):
                continue
            
            current_followers = user.get('followers_count', 0)
            historical_followers = user['historical_metrics'].get('followers_count', current_followers)
            
            # Calculate growth rate
            if historical_followers > 0:
                growth_rate = ((current_followers - historical_followers) / historical_followers) * 100
            else:
                growth_rate = 0
            
            # Check for significant growth (>20% in period)
            if growth_rate > 20 and current_followers > 1000:
                # Calculate current influence
                influence_score = self.calculate_influence_score(user)
                
                rising_profile = {
                    'username': user.get('username'),
                    'name': user.get('name'),
                    'current_followers': current_followers,
                    'growth_rate': round(growth_rate, 2),
                    'followers_gained': current_followers - historical_followers,
                    'current_influence': influence_score,
                    'verified': user.get('verified', False),
                    'expertise': self.classify_expertise(user)
                }
                
                rising_influencers.append(rising_profile)
        
        # Sort by growth rate
        rising_influencers.sort(key=lambda x: x['growth_rate'], reverse=True)
        
        return rising_influencers[:20]  # Return top 20
    
    def generate_kol_report(self, kols: List[Dict]) -> Dict:
        """
        Generate summary report of identified KOLs
        
        Args:
            kols: List of KOL profiles
            
        Returns:
            Summary report
        """
        if not kols:
            return {'total_kols': 0}
        
        # Domain distribution
        domain_counts = defaultdict(int)
        for kol in kols:
            domain_counts[kol.get('primary_domain', 'general')] += 1
        
        # Verification stats
        verified_count = sum(1 for kol in kols if kol.get('verified'))
        
        # Engagement statistics
        engagement_rates = [kol.get('engagement_rate', 0) for kol in kols]
        
        # Influence distribution
        influence_scores = [kol.get('influence_score', 0) for kol in kols]
        
        report = {
            'total_kols': len(kols),
            'verified_kols': verified_count,
            'verification_rate': round((verified_count / len(kols)) * 100, 2),
            'domain_distribution': dict(domain_counts),
            'average_influence': round(np.mean(influence_scores), 2),
            'median_influence': round(np.median(influence_scores), 2),
            'average_engagement': round(np.mean(engagement_rates), 2),
            'total_reach': sum(kol.get('followers_count', 0) for kol in kols),
            'top_kols': kols[:5] if len(kols) >= 5 else kols
        }
        
        return report


# Example usage
if __name__ == "__main__":
    # Database config
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Initialize identifier
    identifier = TwitterKOLIdentifier(db_config)
    
    # Sample user data
    sample_users = [
        {
            'username': 'biotech_expert',
            'name': 'Dr. Bio Expert',
            'followers_count': 50000,
            'following_count': 500,
            'tweets_count': 10000,
            'verified': True,
            'bio': 'Biotech analyst and pharma expert. FDA insights.',
            'location': 'Boston, MA',
            'website': 'https://example.com',
            'created_at': datetime.now() - timedelta(days=1000),
            'recent_tweets': [
                {'text': 'FDA approval expected for new cancer drug', 'like_count': 100, 'retweet_count': 50},
                {'text': 'Clinical trial results are promising', 'like_count': 80, 'retweet_count': 30}
            ]
        },
        {
            'username': 'finance_guru',
            'name': 'Market Analyst',
            'followers_count': 100000,
            'following_count': 1000,
            'tweets_count': 50000,
            'verified': False,
            'bio': 'Stock market analysis and investment strategies',
            'location': 'New York, NY',
            'recent_tweets': [
                {'text': 'Bullish on biotech stocks this quarter', 'like_count': 200, 'retweet_count': 100},
                {'text': 'IPO market heating up', 'like_count': 150, 'retweet_count': 75}
            ]
        },
        {
            'username': 'small_account',
            'name': 'Regular User',
            'followers_count': 500,
            'following_count': 1000,
            'tweets_count': 100,
            'verified': False,
            'bio': 'Just interested in science',
            'recent_tweets': []
        }
    ]
    
    print("KOL Identification Analysis")
    print("="*60)
    
    # Identify KOLs
    kols = identifier.identify_kols(sample_users, min_influence=50)
    
    print(f"\nIdentified {len(kols)} KOLs:")
    for kol in kols:
        print(f"\n@{kol['username']} ({kol['name']})")
        print(f"  Influence Score: {kol['influence_score']}")
        print(f"  Primary Domain: {kol['primary_domain']}")
        print(f"  Followers: {kol['followers_count']:,}")
        print(f"  Engagement Rate: {kol['engagement_rate']:.2f}%")
        print(f"  Verified: {kol['verified']}")
    
    # Generate report
    print("\nKOL Report Summary:")
    print("-"*60)
    report = identifier.generate_kol_report(kols)
    print(f"Total KOLs: {report['total_kols']}")
    print(f"Verified: {report['verified_kols']} ({report['verification_rate']}%)")
    print(f"Average Influence: {report['average_influence']}")
    print(f"Total Reach: {report['total_reach']:,} followers")
    
    if report.get('domain_distribution'):
        print("\nDomain Distribution:")
        for domain, count in report['domain_distribution'].items():
            print(f"  {domain}: {count} KOLs")