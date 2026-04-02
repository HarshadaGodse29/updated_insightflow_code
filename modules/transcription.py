import os
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TranscriptionModule:
    LANGUAGE_NAMES = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'hi': 'Hindi',
        'auto': 'Auto-detected'
    }

    def __init__(self):
        self.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            logger.warning("ASSEMBLYAI_API_KEY not found. Using mock transcription.")
    
    def transcribe_file(self, audio_path, language_code=None, speaker_labels=True):
        try:
            logger.info(f"Transcribing file: {audio_path}")
            
            mock_transcript = {
                "segments": [
                    {
                        "speaker": "Speaker A",
                        "text": "Welcome to the meeting. Today we'll discuss the project timeline.",
                        "start": 0,
                        "end": 5000,
                        "confidence": 0.95
                    },
                    {
                        "speaker": "Speaker B",
                        "text": "Great, let's start with the progress update.",
                        "start": 5000,
                        "end": 8000,
                        "confidence": 0.92
                    }
                ],
                "metadata": {
                    "id": "mock_transcript_123",
                    "duration": 120.5,
                    "duration_formatted": "2:00",
                    "total_words": 25,
                    "speaker_count": 2,
                    "language": "en",
                    "language_name": "English",
                    "confidence": 0.94,
                    "created": datetime.now().isoformat()
                }
            }
            
            return mock_transcript
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")
    
    def get_language_name(self, language_code):
        return self.LANGUAGE_NAMES.get(language_code, language_code)