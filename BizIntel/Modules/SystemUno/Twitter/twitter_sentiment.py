"""
Twitter Sentiment Analysis Module for SystemUno
Uses Twitter-RoBERTa model specifically trained on tweets
"""

import logging
import re
from typing import Dict, List, Tuple, Optional
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import emoji

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterSentimentAnalyzer:
    """
    Sentiment analyzer using Twitter-RoBERTa
    Optimized for Twitter-specific language patterns
    """
    
    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"):
        """
        Initialize Twitter sentiment analyzer
        
        Args:
            model_name: HuggingFace model name (Twitter-RoBERTa by default)
        """
        self.model_name = model_name
        
        logger.info(f"Loading Twitter sentiment model: {model_name}")
        
        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        
        # Set device
        self.device = torch.device("cuda" if torch.cuda.is_available() else 
                                  "mps" if torch.backends.mps.is_available() else "cpu")
        self.model = self.model.to(self.device)
        self.model.eval()
        
        logger.info(f"Model loaded on device: {self.device}")
        
        # Label mapping for Twitter-RoBERTa
        self.label_map = {
            0: "negative",
            1: "neutral", 
            2: "positive"
        }
        
        # Financial sentiment keywords (supplement main model)
        self.financial_positive = {
            'bullish', 'buy', 'long', 'upgrade', 'outperform', 'beat', 
            'exceeded', 'growth', 'profit', 'revenue', 'breakthrough'
        }
        
        self.financial_negative = {
            'bearish', 'sell', 'short', 'downgrade', 'underperform', 'miss',
            'declined', 'loss', 'risk', 'concern', 'failed'
        }
        
    def preprocess_tweet(self, text: str) -> str:
        """
        Preprocess tweet text for sentiment analysis
        
        Args:
            text: Raw tweet text
            
        Returns:
            Preprocessed text
        """
        # Convert emojis to text description
        text = emoji.demojize(text, delimiters=(" ", " "))
        
        # Handle @mentions - replace with generic token
        text = re.sub(r'@\w+', '@user', text)
        
        # Handle URLs - replace with generic token
        text = re.sub(r'http\S+|www.\S+', 'http', text)
        
        # Handle stock tickers - preserve but normalize
        text = re.sub(r'\$([A-Z]+)', r'TICKER_\1', text)
        
        # Handle hashtags - preserve but add space
        text = re.sub(r'#(\w+)', r'# \1', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def analyze_sentiment(self, text: str, 
                         return_all_scores: bool = False) -> Dict[str, float]:
        """
        Analyze sentiment of a single tweet
        
        Args:
            text: Tweet text
            return_all_scores: Return scores for all labels
            
        Returns:
            Dictionary with sentiment results
        """
        # Preprocess
        processed_text = self.preprocess_tweet(text)
        
        # Tokenize
        inputs = self.tokenizer(
            processed_text,
            return_tensors="pt",
            truncation=True,
            max_length=128,  # Twitter max is 280 chars, 128 tokens is enough
            padding=True
        ).to(self.device)
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        
        # Get main sentiment
        predicted_class = np.argmax(probs)
        sentiment_label = self.label_map[predicted_class]
        confidence = float(probs[predicted_class])
        
        # Calculate sentiment score (-1 to 1)
        # Weighted average: negative * -1 + neutral * 0 + positive * 1
        sentiment_score = float(probs[2] - probs[0])
        
        result = {
            'sentiment': sentiment_label,
            'confidence': confidence,
            'score': sentiment_score
        }
        
        if return_all_scores:
            result['scores'] = {
                'negative': float(probs[0]),
                'neutral': float(probs[1]),
                'positive': float(probs[2])
            }
        
        # Add financial sentiment if detected
        financial_sentiment = self._detect_financial_sentiment(text.lower())
        if financial_sentiment:
            result['financial_sentiment'] = financial_sentiment
        
        return result
    
    def analyze_batch(self, texts: List[str], 
                     batch_size: int = 32) -> List[Dict[str, float]]:
        """
        Analyze sentiment for multiple tweets
        
        Args:
            texts: List of tweet texts
            batch_size: Processing batch size
            
        Returns:
            List of sentiment results
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Preprocess batch
            processed_texts = [self.preprocess_tweet(text) for text in batch_texts]
            
            # Tokenize batch
            inputs = self.tokenizer(
                processed_texts,
                return_tensors="pt",
                truncation=True,
                max_length=128,
                padding=True
            ).to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
            
            # Process each result
            for j, (text, prob) in enumerate(zip(batch_texts, probs)):
                predicted_class = np.argmax(prob)
                sentiment_label = self.label_map[predicted_class]
                confidence = float(prob[predicted_class])
                sentiment_score = float(prob[2] - prob[0])
                
                result = {
                    'sentiment': sentiment_label,
                    'confidence': confidence,
                    'score': sentiment_score,
                    'scores': {
                        'negative': float(prob[0]),
                        'neutral': float(prob[1]),
                        'positive': float(prob[2])
                    }
                }
                
                # Add financial sentiment
                financial_sentiment = self._detect_financial_sentiment(text.lower())
                if financial_sentiment:
                    result['financial_sentiment'] = financial_sentiment
                
                results.append(result)
        
        return results
    
    def _detect_financial_sentiment(self, text: str) -> Optional[str]:
        """
        Detect financial sentiment from keywords
        
        Args:
            text: Lowercase tweet text
            
        Returns:
            'bullish', 'bearish', or None
        """
        positive_count = sum(1 for word in self.financial_positive if word in text)
        negative_count = sum(1 for word in self.financial_negative if word in text)
        
        if positive_count > negative_count:
            return 'bullish'
        elif negative_count > positive_count:
            return 'bearish'
        
        return None
    
    def analyze_thread(self, tweets: List[Dict[str, str]]) -> Dict[str, any]:
        """
        Analyze sentiment across a Twitter thread
        
        Args:
            tweets: List of tweet dictionaries with 'text' and 'tweet_id'
            
        Returns:
            Thread-level sentiment analysis
        """
        if not tweets:
            return {}
        
        # Analyze each tweet
        sentiments = []
        for tweet in tweets:
            result = self.analyze_sentiment(tweet['text'], return_all_scores=True)
            result['tweet_id'] = tweet.get('tweet_id')
            sentiments.append(result)
        
        # Calculate thread-level metrics
        scores = [s['score'] for s in sentiments]
        
        thread_sentiment = {
            'tweet_sentiments': sentiments,
            'thread_score': float(np.mean(scores)),
            'thread_std': float(np.std(scores)),
            'thread_trend': self._calculate_trend(scores),
            'dominant_sentiment': self._get_dominant_sentiment(sentiments),
            'sentiment_consistency': self._calculate_consistency(sentiments)
        }
        
        return thread_sentiment
    
    def _calculate_trend(self, scores: List[float]) -> str:
        """Calculate sentiment trend over thread"""
        if len(scores) < 2:
            return 'stable'
        
        # Simple linear regression slope
        x = np.arange(len(scores))
        slope = np.polyfit(x, scores, 1)[0]
        
        if slope > 0.1:
            return 'improving'
        elif slope < -0.1:
            return 'declining'
        else:
            return 'stable'
    
    def _get_dominant_sentiment(self, sentiments: List[Dict]) -> str:
        """Get most common sentiment in thread"""
        labels = [s['sentiment'] for s in sentiments]
        return max(set(labels), key=labels.count)
    
    def _calculate_consistency(self, sentiments: List[Dict]) -> float:
        """Calculate how consistent sentiments are across thread"""
        if len(sentiments) < 2:
            return 1.0
        
        labels = [s['sentiment'] for s in sentiments]
        dominant = self._get_dominant_sentiment(sentiments)
        consistency = labels.count(dominant) / len(labels)
        
        return consistency
    
    def get_sentiment_summary(self, tweet_sentiments: List[Dict]) -> Dict:
        """
        Generate summary statistics for a collection of tweets
        
        Args:
            tweet_sentiments: List of sentiment results
            
        Returns:
            Summary statistics
        """
        if not tweet_sentiments:
            return {}
        
        scores = [s['score'] for s in tweet_sentiments]
        sentiments = [s['sentiment'] for s in tweet_sentiments]
        
        # Count sentiments
        sentiment_counts = {
            'positive': sentiments.count('positive'),
            'neutral': sentiments.count('neutral'),
            'negative': sentiments.count('negative')
        }
        
        # Calculate percentages
        total = len(sentiments)
        sentiment_percentages = {
            k: (v / total * 100) for k, v in sentiment_counts.items()
        }
        
        # Financial sentiment if available
        financial = [s.get('financial_sentiment') for s in tweet_sentiments 
                    if s.get('financial_sentiment')]
        
        summary = {
            'total_tweets': total,
            'sentiment_counts': sentiment_counts,
            'sentiment_percentages': sentiment_percentages,
            'average_score': float(np.mean(scores)),
            'score_std': float(np.std(scores)),
            'score_min': float(np.min(scores)),
            'score_max': float(np.max(scores)),
            'dominant_sentiment': max(sentiment_counts, key=sentiment_counts.get)
        }
        
        if financial:
            summary['financial_sentiment'] = {
                'bullish': financial.count('bullish'),
                'bearish': financial.count('bearish'),
                'dominant': 'bullish' if financial.count('bullish') > financial.count('bearish') else 'bearish'
            }
        
        return summary


# Example usage
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = TwitterSentimentAnalyzer()
    
    # Test tweets
    test_tweets = [
        "Just announced! Our new drug received FDA approval! 🚀 $GRAL",
        "Disappointed with the clinical trial results. Back to the drawing board.",
        "Attending the biotech conference today. Lots of interesting presentations.",
        "Stock is mooning! 🌙 Best investment ever! #bullish $GRAL",
        "Concerning safety signals in the latest data. Need more investigation."
    ]
    
    print("Individual Tweet Analysis:")
    print("-" * 50)
    
    for tweet in test_tweets:
        result = analyzer.analyze_sentiment(tweet, return_all_scores=True)
        print(f"\nTweet: {tweet[:80]}...")
        print(f"Sentiment: {result['sentiment']} (confidence: {result['confidence']:.2f})")
        print(f"Score: {result['score']:.3f}")
        if result.get('financial_sentiment'):
            print(f"Financial: {result['financial_sentiment']}")
    
    # Batch analysis
    print("\n" + "="*50)
    print("Batch Analysis Summary:")
    print("-" * 50)
    
    batch_results = analyzer.analyze_batch(test_tweets)
    summary = analyzer.get_sentiment_summary(batch_results)
    
    print(f"Total tweets: {summary['total_tweets']}")
    print(f"Sentiment distribution: {summary['sentiment_percentages']}")
    print(f"Average score: {summary['average_score']:.3f}")
    print(f"Dominant sentiment: {summary['dominant_sentiment']}")
    
    if summary.get('financial_sentiment'):
        print(f"Financial sentiment: {summary['financial_sentiment']}")