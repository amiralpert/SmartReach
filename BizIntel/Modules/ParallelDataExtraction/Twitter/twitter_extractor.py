"""
Twitter Extractor for SmartReach BizIntel
Extracts Twitter profile snapshots and tweet activity using Twitter API v2
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

import tweepy
from tweepy.errors import TooManyRequests, TwitterServerError
from ..base_extractor import BaseExtractor


class TwitterExtractor(BaseExtractor):
    """Extract Twitter data using API v2"""
    
    # Extractor configuration
    extractor_name = "twitter"
    required_fields = []  # twitter_handle will be checked separately
    rate_limit = "300/15min"  # Twitter API v2 rate limits
    needs_auth = True
    
    def __init__(self, db_config: Dict = None):
        """Initialize Twitter extractor"""
        super().__init__(db_config)
        
        # Twitter API credentials (will be loaded from environment)
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        
        # Initialize Twitter client
        self.client = None
        if self.bearer_token:
            self.client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=False  # Don't wait, fail fast for testing
            )
        else:
            self.logger.warning("Twitter API credentials not found in environment")
        
        # Configuration
        self.initial_tweet_count = 10  # Tweets to fetch on first extraction (LIMITED FOR TESTING)
        self.incremental_tweet_count = 10  # Tweets to fetch on updates (LIMITED FOR TESTING)
        self.lookback_days = 7  # Days to look back for incremental updates
    
    def can_extract(self, company_data: Dict) -> bool:
        """
        Check if Twitter extraction is possible for this company
        
        Args:
            company_data: Company information from database
            
        Returns:
            bool: True if we have a Twitter handle
        """
        # Check for Twitter handle
        twitter_handle = company_data.get('twitter_handle')
        
        # Also check in apollo_data as fallback
        if not twitter_handle:
            apollo_data = company_data.get('apollo_data', {})
            twitter_handle = apollo_data.get('twitter_handle') or apollo_data.get('twitter')
        
        if not twitter_handle:
            self.logger.info(f"No Twitter handle found for {company_data.get('domain')}")
            return False
        
        if not self.client:
            self.logger.error("Twitter API client not initialized")
            return False
        
        return True
    
    def extract_mentions(self, domain: str, handle: str, days_back: int = 7) -> int:
        """
        Extract tweets that mention the company
        
        Args:
            domain: Company domain
            handle: Twitter handle (without @)
            days_back: Number of days to look back
            
        Returns:
            Number of mentions saved
        """
        try:
            # Search for mentions of the company
            start_time = datetime.now() - timedelta(days=days_back)
            
            # Search for @mentions and company name
            query = f"@{handle} OR #{handle}"
            
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=10,  # Limited for testing
                start_time=start_time.isoformat() + 'Z',
                tweet_fields=[
                    'created_at', 'author_id', 'conversation_id', 
                    'referenced_tweets', 'text', 'public_metrics',
                    'entities', 'attachments', 'context_annotations'
                ],
                expansions=[
                    'author_id',
                    'referenced_tweets.id',
                    'entities.mentions.username'
                ],
                user_fields=['username', 'verified', 'public_metrics']
            )
            
            if not tweets.data:
                return 0
            
            mentions_saved = 0
            
            # Get user data from includes
            users = {}
            if hasattr(tweets, 'includes') and hasattr(tweets.includes, 'users'):
                for user in tweets.includes['users']:
                    users[user.id] = user.username
            
            for tweet in tweets.data:
                # Get author handle from user mapping
                author_handle = users.get(tweet.author_id, 'unknown')
                
                # Save as mention in twitter_mentions table
                if self._save_mention(domain, tweet, author_handle):
                    mentions_saved += 1
            
            return mentions_saved
            
        except Exception as e:
            self.logger.error(f"Failed to extract mentions for {handle}: {e}")
            return 0
    
    def _save_mention(self, domain: str, tweet_data, author_handle: str) -> bool:
        """Save a mention to the twitter_mentions table"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get metrics
            metrics = tweet_data.public_metrics if hasattr(tweet_data, 'public_metrics') else {}
            
            # Determine mention type
            mention_type = 'mention'
            if hasattr(tweet_data, 'referenced_tweets'):
                for ref in tweet_data.referenced_tweets:
                    if ref.type == 'replied_to':
                        mention_type = 'reply'
                    elif ref.type == 'quoted':
                        mention_type = 'quote'
            
            cursor.execute("""
                INSERT INTO social.twitter_mentions 
                (company_domain, tweet_id, author_username, author_verified,
                 text, created_at, mention_type, engagement_score,
                 retweet_count, like_count, reply_count, quote_count,
                 raw_data, extracted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tweet_id) DO UPDATE
                SET engagement_score = EXCLUDED.engagement_score,
                    retweet_count = EXCLUDED.retweet_count,
                    like_count = EXCLUDED.like_count,
                    reply_count = EXCLUDED.reply_count,
                    quote_count = EXCLUDED.quote_count,
                    extracted_at = EXCLUDED.extracted_at
            """, (
                domain,
                tweet_data.id,
                author_handle,
                False,  # Verification status would come from user expansion
                tweet_data.text,
                tweet_data.created_at,
                mention_type,
                metrics.get('like_count', 0) + metrics.get('retweet_count', 0) * 2,  # Simple engagement score
                metrics.get('retweet_count', 0),
                metrics.get('like_count', 0),
                metrics.get('reply_count', 0),
                metrics.get('quote_count', 0),
                json.dumps({
                    'id': tweet_data.id,
                    'text': tweet_data.text,
                    'created_at': tweet_data.created_at.isoformat() if tweet_data.created_at else None,
                    'public_metrics': metrics,
                    'entities': tweet_data.entities if hasattr(tweet_data, 'entities') else None
                }),
                datetime.now()
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save mention {tweet_data.id}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def extract(self, company_data: Dict) -> Dict:
        """
        Extract Twitter data for a company
        
        Args:
            company_data: Full company data from database
            
        Returns:
            Dict with extraction results
        """
        domain = company_data['domain']
        company_name = company_data.get('name', domain)
        
        # Get Twitter handle
        twitter_handle = company_data.get('twitter_handle')
        if not twitter_handle:
            apollo_data = company_data.get('apollo_data', {})
            twitter_handle = apollo_data.get('twitter_handle') or apollo_data.get('twitter')
        
        # Clean up handle (remove @ if present)
        if twitter_handle.startswith('@'):
            twitter_handle = twitter_handle[1:]
        
        self.logger.info(f"Extracting Twitter data for {company_name} (@{twitter_handle})")
        
        try:
            # Update company status to extracting
            self._update_twitter_status(domain, 'extracting')
            
            # Extract profile data
            profile_saved = self._extract_profile(domain, twitter_handle)
            
            # Determine extraction mode based on twitter_status
            twitter_status = company_data.get('twitter_status')
            
            # Extract tweets
            if twitter_status == 'complete':
                # Incremental update - get recent tweets only
                tweets_saved = self._extract_tweets_incremental(domain, twitter_handle)
            else:
                # Initial extraction - get more historical data
                tweets_saved = self._extract_tweets_initial(domain, twitter_handle)
            
            # Extract mentions (tweets mentioning this company)
            mentions_saved = self.extract_mentions(domain, twitter_handle, days_back=7)
            
            # Update status to complete
            self._update_twitter_status(domain, 'complete')
            
            self.logger.info(f"Extracted {tweets_saved} tweets and {mentions_saved} mentions for {company_name}")
            
            return {
                'status': 'success',
                'count': tweets_saved + mentions_saved,
                'message': f'Extracted {tweets_saved} tweets, {mentions_saved} mentions, and profile snapshot',
                'data': {
                    'profile_saved': profile_saved,
                    'tweets_saved': tweets_saved,
                    'mentions_saved': mentions_saved
                }
            }
        
        except TooManyRequests as e:
            self.logger.warning(f"Rate limit hit for {domain}: {e}")
            # Don't mark as failed, just skip for now
            return {
                'status': 'skipped',
                'count': 0,
                'message': 'Twitter API rate limit reached. Will retry in next batch.'
            }
            
        except Exception as e:
            self.logger.error(f"Twitter extraction failed for {domain}: {e}")
            self._update_twitter_status(domain, 'failed')
            return {
                'status': 'failed',
                'count': 0,
                'message': str(e)
            }
    
    def _extract_profile(self, domain: str, handle: str) -> bool:
        """Extract and save Twitter profile snapshot"""
        try:
            # Get user data from Twitter API
            user = self.client.get_user(
                username=handle,
                user_fields=[
                    'created_at', 'description', 'entities', 'id', 'location',
                    'name', 'pinned_tweet_id', 'profile_image_url', 'protected',
                    'public_metrics', 'url', 'verified', 'withheld'
                ]
            )
            
            if not user.data:
                self.logger.warning(f"No user found for handle: {handle}")
                return False
            
            user_data = user.data
            
            # Extract metrics
            metrics = user_data.public_metrics or {}
            
            # Save profile snapshot to database
            conn = None
            cursor = None
            
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO twitter_profiles 
                    (company_domain, handle, followers_count, following_count, 
                     tweets_count, listed_count, name, bio, location, website, 
                     verified, profile_image_url, created_at, extracted_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    domain,
                    handle,
                    metrics.get('followers_count', 0),
                    metrics.get('following_count', 0),
                    metrics.get('tweet_count', 0),
                    metrics.get('listed_count', 0),
                    user_data.name,
                    user_data.description,
                    user_data.location,
                    user_data.url,
                    user_data.verified if hasattr(user_data, 'verified') else False,
                    user_data.profile_image_url if hasattr(user_data, 'profile_image_url') else None,
                    user_data.created_at,
                    datetime.now()
                ))
                
                conn.commit()
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to save profile: {e}")
                if conn:
                    conn.rollback()
                return False
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to extract profile for {handle}: {e}")
            return False
    
    def _extract_tweets_initial(self, domain: str, handle: str) -> int:
        """Extract initial set of tweets (more historical data)"""
        try:
            # Get user ID first
            user = self.client.get_user(username=handle)
            if not user.data:
                return 0
            
            user_id = user.data.id
            
            # Get timeline tweets with full entity data
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=10,  # Limited for testing (normally 100)
                tweet_fields=[
                    'created_at', 'author_id', 'conversation_id', 'in_reply_to_user_id',
                    'referenced_tweets', 'text', 'withheld', 'public_metrics',
                    'possibly_sensitive', 'lang', 'reply_settings', 'entities',
                    'attachments', 'context_annotations', 'geo'
                ],
                expansions=[
                    'referenced_tweets.id', 
                    'in_reply_to_user_id',
                    'entities.mentions.username',
                    'attachments.media_keys'
                ],
                media_fields=['type', 'url', 'preview_image_url'],
                exclude=['retweets']  # We'll get retweets separately if needed
            )
            
            if not tweets.data:
                return 0
            
            tweets_saved = 0
            
            # Process in pages (Twitter paginates results)
            for tweet in tweets.data:
                if self._save_tweet(domain, handle, tweet):
                    tweets_saved += 1
            
            # Get next page if we haven't reached our target
            pagination_token = tweets.meta.get('next_token')
            total_fetched = tweets_saved
            
            while pagination_token and total_fetched < self.initial_tweet_count:
                # Rate limit protection
                time.sleep(1)
                
                # Get next page with full entity data
                tweets = self.client.get_users_tweets(
                    id=user_id,
                    max_results=100,
                    pagination_token=pagination_token,
                    tweet_fields=[
                        'created_at', 'author_id', 'conversation_id', 'in_reply_to_user_id',
                        'referenced_tweets', 'text', 'withheld', 'public_metrics',
                        'entities', 'attachments', 'context_annotations', 'geo'
                    ],
                    expansions=[
                        'referenced_tweets.id',
                        'in_reply_to_user_id',
                        'entities.mentions.username',
                        'attachments.media_keys'
                    ],
                    media_fields=['type', 'url', 'preview_image_url'],
                    exclude=['retweets']
                )
                
                if not tweets.data:
                    break
                
                for tweet in tweets.data:
                    if self._save_tweet(domain, handle, tweet):
                        tweets_saved += 1
                        total_fetched += 1
                
                pagination_token = tweets.meta.get('next_token')
            
            return tweets_saved
            
        except Exception as e:
            self.logger.error(f"Failed to extract tweets for {handle}: {e}")
            return 0
    
    def _extract_tweets_incremental(self, domain: str, handle: str) -> int:
        """Extract recent tweets since last extraction"""
        try:
            # Get last extraction timestamp
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT MAX(created_at) 
                FROM twitter_activity 
                WHERE company_domain = %s
            """, (domain,))
            
            last_tweet = cursor.fetchone()
            cursor.close()
            conn.close()
            
            # Determine start time for incremental fetch
            if last_tweet and last_tweet[0]:
                start_time = last_tweet[0]
            else:
                # No previous tweets, get last N days
                start_time = datetime.now() - timedelta(days=self.lookback_days)
            
            # Get user ID
            user = self.client.get_user(username=handle)
            if not user.data:
                return 0
            
            user_id = user.data.id
            
            # Get recent tweets since last extraction with full entity data
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=self.incremental_tweet_count,
                start_time=start_time.isoformat() + 'Z' if start_time else None,
                tweet_fields=[
                    'created_at', 'author_id', 'conversation_id', 'in_reply_to_user_id',
                    'referenced_tweets', 'text', 'withheld', 'public_metrics',
                    'entities', 'attachments', 'context_annotations', 'geo'
                ],
                expansions=[
                    'referenced_tweets.id',
                    'in_reply_to_user_id',
                    'entities.mentions.username',
                    'attachments.media_keys'
                ],
                media_fields=['type', 'url', 'preview_image_url'],
                exclude=['retweets']
            )
            
            if not tweets.data:
                return 0
            
            tweets_saved = 0
            for tweet in tweets.data:
                if self._save_tweet(domain, handle, tweet):
                    tweets_saved += 1
            
            return tweets_saved
            
        except Exception as e:
            self.logger.error(f"Failed incremental extraction for {handle}: {e}")
            return 0
    
    def _save_tweet(self, domain: str, handle: str, tweet_data) -> bool:
        """Save a single tweet to the database"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Determine tweet type
            tweet_type = 'tweet'
            in_reply_to_tweet_id = None
            in_reply_to_user_handle = None
            retweeted_tweet_id = None
            quoted_tweet_id = None
            
            # Check for referenced tweets to determine type
            if hasattr(tweet_data, 'referenced_tweets') and tweet_data.referenced_tweets:
                for ref in tweet_data.referenced_tweets:
                    if ref.type == 'replied_to':
                        tweet_type = 'reply'
                        in_reply_to_tweet_id = ref.id
                    elif ref.type == 'retweeted':
                        tweet_type = 'retweet'
                        retweeted_tweet_id = ref.id
                    elif ref.type == 'quoted':
                        tweet_type = 'quote'
                        quoted_tweet_id = ref.id
            
            # Get metrics
            metrics = tweet_data.public_metrics if hasattr(tweet_data, 'public_metrics') else {}
            
            # Extract entities (mentions, hashtags, URLs, media)
            entities = tweet_data.entities if hasattr(tweet_data, 'entities') else {}
            
            # Extract mentions
            user_mentions = []
            if 'mentions' in entities:
                user_mentions = [mention.get('username', '') for mention in entities['mentions']]
            
            # Extract hashtags
            hashtags = []
            if 'hashtags' in entities:
                hashtags = [tag.get('tag', '') for tag in entities['hashtags']]
            
            # Extract URLs
            urls = []
            if 'urls' in entities:
                urls = [url.get('expanded_url', url.get('url', '')) for url in entities['urls']]
            
            # Extract media information
            has_media = False
            media_types = []
            media_urls = []
            if hasattr(tweet_data, 'attachments') and tweet_data.attachments:
                if 'media_keys' in tweet_data.attachments:
                    has_media = True
                    # Note: Actual media data would come from expansions.media
                    # For now, just note that media exists
                    media_types = ['media']  # Would need to get from expanded media
            
            # Build raw JSON for future analysis
            raw_json = {
                'id': tweet_data.id,
                'text': tweet_data.text,
                'created_at': tweet_data.created_at.isoformat() if tweet_data.created_at else None,
                'author_id': tweet_data.author_id if hasattr(tweet_data, 'author_id') else None,
                'conversation_id': tweet_data.conversation_id if hasattr(tweet_data, 'conversation_id') else None,
                'in_reply_to_user_id': tweet_data.in_reply_to_user_id if hasattr(tweet_data, 'in_reply_to_user_id') else None,
                'referenced_tweets': [{'type': ref.type, 'id': ref.id} for ref in (tweet_data.referenced_tweets or [])] if hasattr(tweet_data, 'referenced_tweets') else [],
                'public_metrics': metrics,
                'lang': tweet_data.lang if hasattr(tweet_data, 'lang') else None,
                'possibly_sensitive': tweet_data.possibly_sensitive if hasattr(tweet_data, 'possibly_sensitive') else None,
                'entities': entities,
                'attachments': tweet_data.attachments.__dict__ if hasattr(tweet_data, 'attachments') and tweet_data.attachments else None,
                'context_annotations': tweet_data.context_annotations if hasattr(tweet_data, 'context_annotations') else None
            }
            
            cursor.execute("""
                INSERT INTO twitter_activity 
                (company_domain, tweet_id, tweet_type, text, author_handle, created_at,
                 retweet_count, reply_count, like_count, quote_count,
                 in_reply_to_tweet_id, in_reply_to_user_handle, 
                 retweeted_tweet_id, quoted_tweet_id, raw_json, extracted_at,
                 has_media, media_types, media_urls, hashtags, user_mentions, urls)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tweet_id) DO UPDATE
                SET retweet_count = EXCLUDED.retweet_count,
                    reply_count = EXCLUDED.reply_count,
                    like_count = EXCLUDED.like_count,
                    quote_count = EXCLUDED.quote_count,
                    raw_json = EXCLUDED.raw_json,
                    extracted_at = EXCLUDED.extracted_at,
                    has_media = EXCLUDED.has_media,
                    media_types = EXCLUDED.media_types,
                    media_urls = EXCLUDED.media_urls,
                    hashtags = EXCLUDED.hashtags,
                    user_mentions = EXCLUDED.user_mentions,
                    urls = EXCLUDED.urls
            """, (
                domain,
                tweet_data.id,
                tweet_type,
                tweet_data.text,
                handle,
                tweet_data.created_at,
                metrics.get('retweet_count', 0),
                metrics.get('reply_count', 0),
                metrics.get('like_count', 0),
                metrics.get('quote_count', 0),
                in_reply_to_tweet_id,
                in_reply_to_user_handle,
                retweeted_tweet_id,
                quoted_tweet_id,
                json.dumps(raw_json),
                datetime.now(),
                has_media,
                media_types if media_types else None,
                media_urls if media_urls else None,
                hashtags if hashtags else None,
                user_mentions if user_mentions else None,
                urls if urls else None
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save tweet {tweet_data.id}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _update_twitter_status(self, domain: str, status: str) -> None:
        """Update twitter_status in companies table"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE companies 
                SET twitter_status = %s, updated_at = %s
                WHERE domain = %s
            """, (status, datetime.now(), domain))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to update twitter_status: {e}")
            if conn:
                conn.rollback()
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
    load_dotenv(env_path)
    
    # Get domain from command line or use default
    domain = sys.argv[1] if len(sys.argv) > 1 else "pfizer.com"
    
    # Create extractor and run
    extractor = TwitterExtractor()
    
    # First, let's update a test company with a Twitter handle for testing
    if len(sys.argv) > 2:
        # If a handle is provided, update the company
        handle = sys.argv[2]
        conn = extractor.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE companies 
            SET twitter_handle = %s 
            WHERE domain = %s
        """, (handle, domain))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Updated {domain} with Twitter handle: {handle}")
    
    # Run extraction
    result = extractor.run(domain)
    print(f"Twitter Extraction Result: {json.dumps(result, indent=2)}")