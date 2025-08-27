"""
Twitter Engagement Analysis Module for SystemUno
Analyzes engagement patterns, viral content, and optimal posting times
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from collections import defaultdict
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterEngagementAnalyzer:
    """
    Analyzes Twitter engagement metrics and patterns
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize engagement analyzer
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config
        
        # Engagement weights for scoring
        self.engagement_weights = {
            'like': 1.0,
            'retweet': 2.0,
            'reply': 3.0,
            'quote': 4.0
        }
        
        # Viral detection parameters
        self.viral_threshold_multiplier = 100.0  # 100x baseline
        self.viral_min_engagements = 100  # Minimum absolute engagements
    
    def calculate_engagement_rate(self, tweet_data: Dict) -> float:
        """
        Calculate engagement rate for a tweet
        
        Args:
            tweet_data: Tweet metrics dictionary
            
        Returns:
            Engagement rate (0-100)
        """
        # Get metrics
        likes = tweet_data.get('like_count', 0)
        retweets = tweet_data.get('retweet_count', 0)
        replies = tweet_data.get('reply_count', 0)
        quotes = tweet_data.get('quote_count', 0)
        
        # Calculate weighted engagement
        weighted_engagement = (
            likes * self.engagement_weights['like'] +
            retweets * self.engagement_weights['retweet'] +
            replies * self.engagement_weights['reply'] +
            quotes * self.engagement_weights['quote']
        )
        
        # Get impressions or estimate from followers
        impressions = tweet_data.get('impression_count')
        if not impressions:
            # Estimate impressions from followers (rough approximation)
            followers = tweet_data.get('author_followers', 1000)
            impressions = followers * 0.1  # Assume 10% reach
        
        # Calculate rate
        if impressions > 0:
            rate = (weighted_engagement / impressions) * 100
            return min(rate, 100)  # Cap at 100%
        
        return 0.0
    
    def detect_viral_content(self, 
                           tweets: List[Dict],
                           baseline_stats: Optional[Dict] = None) -> List[Dict]:
        """
        Detect viral or potentially viral content
        
        Args:
            tweets: List of tweet data
            baseline_stats: Baseline engagement statistics
            
        Returns:
            List of viral tweets with analysis
        """
        if not tweets:
            return []
        
        # Calculate baseline if not provided
        if not baseline_stats:
            baseline_stats = self._calculate_baseline_stats(tweets)
        
        viral_tweets = []
        
        for tweet in tweets:
            # Calculate total engagement
            total_engagement = (
                tweet.get('like_count', 0) +
                tweet.get('retweet_count', 0) +
                tweet.get('reply_count', 0) +
                tweet.get('quote_count', 0)
            )
            
            # Check absolute threshold
            if total_engagement < self.viral_min_engagements:
                continue
            
            # Check relative threshold (compared to baseline)
            if total_engagement > baseline_stats['mean_engagement'] * self.viral_threshold_multiplier:
                viral_analysis = {
                    'tweet_id': tweet.get('tweet_id'),
                    'text': tweet.get('text', '')[:100] + '...',
                    'total_engagement': total_engagement,
                    'viral_multiplier': total_engagement / max(baseline_stats['mean_engagement'], 1),
                    'engagement_breakdown': {
                        'likes': tweet.get('like_count', 0),
                        'retweets': tweet.get('retweet_count', 0),
                        'replies': tweet.get('reply_count', 0),
                        'quotes': tweet.get('quote_count', 0)
                    },
                    'created_at': tweet.get('created_at'),
                    'viral_score': self._calculate_viral_score(tweet, baseline_stats)
                }
                viral_tweets.append(viral_analysis)
        
        # Sort by viral score
        viral_tweets.sort(key=lambda x: x['viral_score'], reverse=True)
        
        return viral_tweets
    
    def _calculate_viral_score(self, tweet: Dict, baseline: Dict) -> float:
        """
        Calculate a viral score (0-100) for a tweet
        
        Args:
            tweet: Tweet data
            baseline: Baseline statistics
            
        Returns:
            Viral score
        """
        score_components = []
        
        # Engagement velocity (how fast it's gaining engagement)
        hours_since_post = 24  # Default if not available
        if tweet.get('created_at'):
            try:
                created = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                hours_since_post = max((datetime.now() - created).total_seconds() / 3600, 1)
            except:
                pass
        
        engagement_per_hour = (tweet.get('like_count', 0) + tweet.get('retweet_count', 0)) / hours_since_post
        velocity_score = min(engagement_per_hour / 100, 1.0) * 30  # Max 30 points
        score_components.append(velocity_score)
        
        # Relative engagement (compared to baseline)
        total_engagement = sum([
            tweet.get('like_count', 0),
            tweet.get('retweet_count', 0),
            tweet.get('reply_count', 0),
            tweet.get('quote_count', 0)
        ])
        
        relative_score = min(total_engagement / max(baseline['mean_engagement'] * 10, 1), 1.0) * 40  # Max 40 points
        score_components.append(relative_score)
        
        # Engagement quality (replies and quotes are higher quality)
        quality_engagement = tweet.get('reply_count', 0) + tweet.get('quote_count', 0)
        quality_score = min(quality_engagement / 50, 1.0) * 30  # Max 30 points
        score_components.append(quality_score)
        
        return sum(score_components)
    
    def _calculate_baseline_stats(self, tweets: List[Dict]) -> Dict:
        """
        Calculate baseline engagement statistics
        
        Args:
            tweets: List of tweet data
            
        Returns:
            Baseline statistics
        """
        if not tweets:
            return {
                'mean_engagement': 0,
                'median_engagement': 0,
                'std_engagement': 0,
                'percentile_95': 0
            }
        
        engagements = []
        for tweet in tweets:
            total = (
                tweet.get('like_count', 0) +
                tweet.get('retweet_count', 0) +
                tweet.get('reply_count', 0) +
                tweet.get('quote_count', 0)
            )
            engagements.append(total)
        
        return {
            'mean_engagement': np.mean(engagements),
            'median_engagement': np.median(engagements),
            'std_engagement': np.std(engagements),
            'percentile_95': np.percentile(engagements, 95)
        }
    
    def analyze_optimal_timing(self, tweets: List[Dict]) -> Dict:
        """
        Analyze optimal posting times based on engagement
        
        Args:
            tweets: List of tweet data with timestamps
            
        Returns:
            Optimal timing analysis
        """
        if not tweets:
            return {}
        
        # Group by hour and day of week
        hourly_engagement = defaultdict(list)
        daily_engagement = defaultdict(list)
        day_hour_engagement = defaultdict(list)
        
        for tweet in tweets:
            if not tweet.get('created_at'):
                continue
            
            try:
                created = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                hour = created.hour
                day = created.weekday()  # 0 = Monday, 6 = Sunday
                
                engagement = (
                    tweet.get('like_count', 0) +
                    tweet.get('retweet_count', 0) +
                    tweet.get('reply_count', 0) +
                    tweet.get('quote_count', 0)
                )
                
                hourly_engagement[hour].append(engagement)
                daily_engagement[day].append(engagement)
                day_hour_engagement[(day, hour)].append(engagement)
                
            except Exception as e:
                logger.warning(f"Error parsing timestamp: {e}")
                continue
        
        # Calculate averages
        best_hours = []
        for hour, engagements in hourly_engagement.items():
            avg_engagement = np.mean(engagements)
            best_hours.append({
                'hour': hour,
                'average_engagement': avg_engagement,
                'tweet_count': len(engagements)
            })
        
        best_hours.sort(key=lambda x: x['average_engagement'], reverse=True)
        
        best_days = []
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day, engagements in daily_engagement.items():
            avg_engagement = np.mean(engagements)
            best_days.append({
                'day': day_names[day],
                'day_number': day,
                'average_engagement': avg_engagement,
                'tweet_count': len(engagements)
            })
        
        best_days.sort(key=lambda x: x['average_engagement'], reverse=True)
        
        # Find best day-hour combinations
        best_slots = []
        for (day, hour), engagements in day_hour_engagement.items():
            if len(engagements) >= 2:  # Need at least 2 data points
                avg_engagement = np.mean(engagements)
                best_slots.append({
                    'day': day_names[day],
                    'hour': hour,
                    'average_engagement': avg_engagement,
                    'tweet_count': len(engagements)
                })
        
        best_slots.sort(key=lambda x: x['average_engagement'], reverse=True)
        
        return {
            'best_hours': best_hours[:5],
            'best_days': best_days[:3],
            'best_time_slots': best_slots[:10],
            'recommendations': self._generate_timing_recommendations(best_hours, best_days, best_slots)
        }
    
    def _generate_timing_recommendations(self, 
                                        best_hours: List[Dict],
                                        best_days: List[Dict],
                                        best_slots: List[Dict]) -> List[str]:
        """
        Generate timing recommendations based on analysis
        
        Args:
            best_hours: Top performing hours
            best_days: Top performing days
            best_slots: Top performing day-hour combinations
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if best_hours:
            top_hour = best_hours[0]['hour']
            recommendations.append(f"Post around {top_hour}:00 for highest engagement")
        
        if best_days:
            top_day = best_days[0]['day']
            recommendations.append(f"{top_day} shows the highest average engagement")
        
        if best_slots and len(best_slots) >= 3:
            slot = best_slots[0]
            recommendations.append(
                f"Best time slot: {slot['day']} at {slot['hour']}:00"
            )
        
        # Check for patterns
        if best_hours:
            morning = [h for h in best_hours[:5] if 6 <= h['hour'] <= 11]
            afternoon = [h for h in best_hours[:5] if 12 <= h['hour'] <= 17]
            evening = [h for h in best_hours[:5] if 18 <= h['hour'] <= 23]
            
            if len(morning) >= 2:
                recommendations.append("Morning posts (6-11 AM) perform well")
            elif len(afternoon) >= 2:
                recommendations.append("Afternoon posts (12-5 PM) perform well")
            elif len(evening) >= 2:
                recommendations.append("Evening posts (6-11 PM) perform well")
        
        return recommendations
    
    def analyze_content_types(self, tweets: List[Dict]) -> Dict:
        """
        Analyze engagement by content type
        
        Args:
            tweets: List of tweet data
            
        Returns:
            Content type analysis
        """
        content_types = {
            'text_only': {'tweets': [], 'engagement': []},
            'with_media': {'tweets': [], 'engagement': []},
            'with_links': {'tweets': [], 'engagement': []},
            'with_hashtags': {'tweets': [], 'engagement': []},
            'replies': {'tweets': [], 'engagement': []},
            'quotes': {'tweets': [], 'engagement': []}
        }
        
        for tweet in tweets:
            engagement = (
                tweet.get('like_count', 0) +
                tweet.get('retweet_count', 0) +
                tweet.get('reply_count', 0) +
                tweet.get('quote_count', 0)
            )
            
            # Categorize tweet
            if tweet.get('has_media'):
                content_types['with_media']['tweets'].append(tweet)
                content_types['with_media']['engagement'].append(engagement)
            elif tweet.get('urls') and len(tweet.get('urls', [])) > 0:
                content_types['with_links']['tweets'].append(tweet)
                content_types['with_links']['engagement'].append(engagement)
            else:
                content_types['text_only']['tweets'].append(tweet)
                content_types['text_only']['engagement'].append(engagement)
            
            if tweet.get('hashtags') and len(tweet.get('hashtags', [])) > 0:
                content_types['with_hashtags']['tweets'].append(tweet)
                content_types['with_hashtags']['engagement'].append(engagement)
            
            if tweet.get('tweet_type') == 'reply':
                content_types['replies']['tweets'].append(tweet)
                content_types['replies']['engagement'].append(engagement)
            elif tweet.get('tweet_type') == 'quote':
                content_types['quotes']['tweets'].append(tweet)
                content_types['quotes']['engagement'].append(engagement)
        
        # Calculate statistics for each type
        analysis = {}
        for content_type, data in content_types.items():
            if data['engagement']:
                analysis[content_type] = {
                    'tweet_count': len(data['tweets']),
                    'average_engagement': np.mean(data['engagement']),
                    'median_engagement': np.median(data['engagement']),
                    'max_engagement': np.max(data['engagement']),
                    'total_engagement': np.sum(data['engagement'])
                }
        
        # Find best performing type
        if analysis:
            best_type = max(analysis.items(), key=lambda x: x[1]['average_engagement'])
            analysis['best_performing'] = best_type[0]
            analysis['recommendations'] = self._generate_content_recommendations(analysis)
        
        return analysis
    
    def _generate_content_recommendations(self, analysis: Dict) -> List[str]:
        """
        Generate content recommendations based on analysis
        
        Args:
            analysis: Content type analysis
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Compare media vs text
        if 'with_media' in analysis and 'text_only' in analysis:
            media_avg = analysis['with_media']['average_engagement']
            text_avg = analysis['text_only']['average_engagement']
            
            if media_avg > text_avg * 1.5:
                recommendations.append("Media content gets 50%+ more engagement")
            elif text_avg > media_avg * 1.5:
                recommendations.append("Text-only content performs better for your audience")
        
        # Check hashtag effectiveness
        if 'with_hashtags' in analysis:
            hashtag_avg = analysis['with_hashtags']['average_engagement']
            overall_avg = np.mean([v['average_engagement'] for v in analysis.values() if isinstance(v, dict)])
            
            if hashtag_avg > overall_avg * 1.2:
                recommendations.append("Using hashtags increases engagement by 20%+")
        
        # Check reply/quote performance
        if 'replies' in analysis and analysis['replies']['tweet_count'] > 5:
            recommendations.append(f"Replies average {analysis['replies']['average_engagement']:.0f} engagements")
        
        if 'quotes' in analysis and analysis['quotes']['tweet_count'] > 3:
            recommendations.append(f"Quote tweets average {analysis['quotes']['average_engagement']:.0f} engagements")
        
        return recommendations
    
    def calculate_audience_quality(self, followers_data: List[Dict]) -> Dict:
        """
        Analyze audience quality based on follower metrics
        
        Args:
            followers_data: List of follower data
            
        Returns:
            Audience quality metrics
        """
        if not followers_data:
            return {'quality_score': 0, 'analysis': {}}
        
        quality_metrics = {
            'verified_ratio': 0,
            'active_ratio': 0,
            'engagement_ratio': 0,
            'follower_following_ratio': 0,
            'bot_likelihood': []
        }
        
        verified_count = 0
        active_count = 0
        suspicious_count = 0
        
        for follower in followers_data:
            # Check verification
            if follower.get('verified'):
                verified_count += 1
            
            # Check activity (has tweets)
            if follower.get('tweet_count', 0) > 10:
                active_count += 1
            
            # Check for bot-like behavior
            followers = follower.get('followers_count', 0)
            following = follower.get('following_count', 0)
            
            # Suspicious patterns
            if following > 0 and followers / following < 0.1:  # Following way more than followers
                suspicious_count += 1
            elif follower.get('tweet_count', 0) == 0 and followers < 10:  # No tweets, few followers
                suspicious_count += 1
        
        total = len(followers_data)
        
        quality_metrics['verified_ratio'] = verified_count / total
        quality_metrics['active_ratio'] = active_count / total
        quality_metrics['suspicious_ratio'] = suspicious_count / total
        
        # Calculate overall quality score (0-100)
        quality_score = (
            quality_metrics['verified_ratio'] * 30 +  # Verification worth 30 points
            quality_metrics['active_ratio'] * 50 +     # Activity worth 50 points
            (1 - quality_metrics['suspicious_ratio']) * 20  # Non-suspicious worth 20 points
        )
        
        return {
            'quality_score': round(quality_score, 2),
            'metrics': quality_metrics,
            'analysis': {
                'verified_followers': verified_count,
                'active_followers': active_count,
                'suspicious_accounts': suspicious_count,
                'total_analyzed': total
            }
        }


# Example usage
if __name__ == "__main__":
    # Database config
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Initialize analyzer
    analyzer = TwitterEngagementAnalyzer(db_config)
    
    # Sample tweet data
    sample_tweets = [
        {
            'tweet_id': '1',
            'text': 'Breaking: FDA approval for our new drug!',
            'like_count': 500,
            'retweet_count': 200,
            'reply_count': 50,
            'quote_count': 30,
            'created_at': '2025-01-15T10:30:00Z',
            'has_media': False,
            'hashtags': ['FDA', 'biotech'],
            'tweet_type': 'tweet'
        },
        {
            'tweet_id': '2',
            'text': 'Clinical trial update',
            'like_count': 50,
            'retweet_count': 10,
            'reply_count': 5,
            'quote_count': 2,
            'created_at': '2025-01-15T14:00:00Z',
            'has_media': True,
            'hashtags': [],
            'tweet_type': 'tweet'
        },
        {
            'tweet_id': '3',
            'text': 'Thank you for your support!',
            'like_count': 100,
            'retweet_count': 20,
            'reply_count': 30,
            'quote_count': 5,
            'created_at': '2025-01-15T18:00:00Z',
            'has_media': False,
            'hashtags': [],
            'tweet_type': 'reply'
        }
    ]
    
    print("Engagement Analysis")
    print("="*60)
    
    # Calculate engagement rates
    print("\nEngagement Rates:")
    for tweet in sample_tweets:
        tweet['author_followers'] = 10000  # Add follower count for calculation
        rate = analyzer.calculate_engagement_rate(tweet)
        print(f"Tweet {tweet['tweet_id']}: {rate:.2f}% engagement rate")
    
    # Detect viral content
    print("\nViral Content Detection:")
    viral = analyzer.detect_viral_content(sample_tweets)
    if viral:
        for v in viral:
            print(f"- Tweet {v['tweet_id']}: {v['viral_multiplier']:.1f}x baseline, Score: {v['viral_score']:.1f}")
    else:
        print("No viral content detected")
    
    # Analyze optimal timing
    print("\nOptimal Timing Analysis:")
    timing = analyzer.analyze_optimal_timing(sample_tweets)
    if timing.get('recommendations'):
        for rec in timing['recommendations']:
            print(f"- {rec}")
    
    # Analyze content types
    print("\nContent Type Analysis:")
    content = analyzer.analyze_content_types(sample_tweets)
    if content.get('best_performing'):
        print(f"Best performing: {content['best_performing']}")
    if content.get('recommendations'):
        for rec in content['recommendations']:
            print(f"- {rec}")