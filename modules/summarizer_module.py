import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SummarizerModule:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found. Using mock summarizer.")
    
    def summarize(self, transcript_text, summary_type="executive", length="medium"):
        """Generate summary (mock version for testing)"""
        try:
            if not transcript_text:
                raise ValueError("Transcript text is empty")
            
            logger.info(f"Generating {summary_type} summary")
            
            # Mock summary
            mock_summary = f"""
EXECUTIVE SUMMARY:
This meeting covered the project timeline and progress updates. The team is on track with deliverables.

KEY DECISIONS:
- Project deadline extended by one week
- Additional resources allocated to the frontend team

ACTION ITEMS:
- Update project documentation - John by Friday
- Review code changes - Sarah by Wednesday

KEY TAKEAWAYS:
- Team is making good progress
- Need to focus on testing next week
"""
            
            return {
                "success": True,
                "summary": mock_summary,
                "title": transcript_text[:100] if transcript_text else "Meeting Summary",
                "metadata": {
                    "type": summary_type,
                    "length": length,
                    "word_count": len(mock_summary.split()),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return {"success": False, "error": str(e)}