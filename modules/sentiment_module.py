from textblob import TextBlob

class SentimentModule:
    def __init__(self):
        pass

    def analyze(self, text):
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity

            if polarity > 0:
                sentiment = "Positive"
            elif polarity < 0:
                sentiment = "Negative"
            else:
                sentiment = "Neutral"

            return {
                "sentiment": sentiment,
                "polarity_score": round(polarity, 2)
            }

        except Exception as e:
            return f"Sentiment Error: {str(e)}"