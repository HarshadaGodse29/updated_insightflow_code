from textblob import TextBlob
import logging

logger = logging.getLogger(__name__)

class SentimentModule:
    def __init__(self):
        logger.info("SentimentModule initialized")
    
    def analyze(self, text):
        try:
            if not text:
                return {"sentiment": "Neutral", "polarity_score": 0.0}
            
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            
            if polarity > 0.1:
                sentiment = "Positive"
            elif polarity < -0.1:
                sentiment = "Negative"
            else:
                sentiment = "Neutral"
            
            return {
                "sentiment": sentiment,
                "polarity_score": round(polarity, 2)
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return {"sentiment": "Neutral", "polarity_score": 0.0}