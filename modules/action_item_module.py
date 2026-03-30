import os
import json
import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


@dataclass
class ActionItem:
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    priority: Optional[str] = None
    source_text: str = ""


class ActionItemModule:

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in .env")

        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile"
        logger.info("ActionItemModule initialized")

    def extract(self, transcript: str) -> List[ActionItem]:
        if not transcript.strip():
            raise ValueError("Transcript is empty")

        prompt = f"""
Extract ONLY real, explicit, assigned action items from the transcript.

Transcript:
{transcript[:12000]}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )

            raw_output = response.choices[0].message.content.strip()
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

            items_data = json.loads(raw_output)
            items = []

            for item in items_data:
                items.append(
                    ActionItem(
                        task=item.get("task", ""),
                        assignee=item.get("assignee"),
                        deadline=item.get("deadline"),
                        priority=item.get("priority"),
                        source_text=item.get("source_text", "")
                    )
                )

            return items

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {raw_output}")
            # Return empty list on parse error
            return []
        except Exception as e:
            logger.error(f"Action item extraction failed: {str(e)}")
            return []