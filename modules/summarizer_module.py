import os
import json
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

class SummarizerModule:

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY missing from environment variables")

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        logger.info("SummarizerModule initialized successfully")

    def summarize(self, transcript_text: str, summary_type: str = "executive", length: str = "medium", include_key_points: bool = True):
        """
        Generate a structured summary based on type and length
        
        Args:
            transcript_text (str): The transcript to summarize
            summary_type (str): Type of summary - "executive", "detailed", or "bullet"
            length (str): Length preference - "short", "medium", or "long"
            include_key_points (bool): Whether to include key decisions and action items
        
        Returns:
            dict: Structured summary with sections
        """
        try:
            if not transcript_text or not transcript_text.strip():
                raise ValueError("Transcript text is empty")

            prompt = self._build_prompt(transcript_text, summary_type, length, include_key_points)
            
            logger.info(f"Generating {summary_type} summary with {length} length")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(summary_type)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=self._get_max_tokens(length)
            )

            if not response or not response.choices:
                raise ValueError("No response from Groq API")

            summary_text = response.choices[0].message.content.strip()
            
            if not summary_text:
                raise ValueError("Empty summary generated")

            structured_summary = self._structure_summary(summary_text, summary_type)
            
            return {
                "success": True,
                "summary": structured_summary,
                "title": title,
                "metadata": {
                    "type": summary_type,
                    "length": length,
                    "include_key_points": include_key_points,
                    "word_count": self._count_words(summary_text),
                    "timestamp": datetime.now().isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _build_prompt(self, text, summary_type, length, include_key_points):
        """Build the prompt based on parameters"""
        
        length_instructions = {
            "short": "Keep it extremely concise (maximum 2-3 sentences). Focus only on the most critical point.",
            "medium": "Provide a balanced summary (4-6 sentences). Cover the main points clearly.",
            "long": "Provide a comprehensive summary (7-10 sentences). Include relevant details and context."
        }
        
        type_instructions = {
            "executive": """
Please create an EXECUTIVE SUMMARY with the following sections:

EXECUTIVE SUMMARY:
[Write 2-3 sentences summarizing the main topic and overall outcome]

KEY DECISIONS:
- [List the main decisions made during the meeting]
- [Each decision should be clear and actionable]

ACTION ITEMS:
- [Task] - [Assignee if mentioned, otherwise use "Unassigned"]
- [Include deadlines if mentioned]

KEY TAKEAWAYS:
- [List the most important takeaways from the discussion]

Make each section clear and well-formatted. Use bullet points with dashes (-) for lists.
""",
        }

        key_points_instruction = """
Additionally, please identify and highlight any:
- Critical decisions made
- Action items with assignees
- Important deadlines mentioned
- Key questions raised
""" if include_key_points else ""

        max_chars = 12000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        prompt = f"""Please summarize the following meeting transcript.

SUMMARY TYPE: {summary_type.upper()}
LENGTH: {length.upper()}

{type_instructions[summary_type]}

LENGTH REQUIREMENT: {length_instructions[length]}

{key_points_instruction}

TRANSCRIPT:
{text}

Generate a well-structured, professional summary following the exact format specified above. Do not use any emojis or special characters. Use simple dashes (-) for bullet points.
"""
        return prompt

    def _get_system_prompt(self, summary_type):
        """Get system prompt based on summary type"""
        base_prompt = """You are an expert meeting summarizer. Your task is to create clear, concise, and well-structured summaries.
Always use proper formatting. Be accurate and focus on key information. Never use emojis or special characters."""
        
        if summary_type == "executive":
            return base_prompt + " Focus on high-level decisions, outcomes, and action items. Be concise but comprehensive."
        elif summary_type == "detailed":
            return base_prompt + " Provide thorough coverage of all important points, discussions, and conclusions."
        else:
            return base_prompt + " Create clear, scannable bullet points that capture the essence of the discussion."

    def _get_max_tokens(self, length):
        """Get max tokens based on length preference"""
        return {
            "short": 300,
            "medium": 600,
            "long": 1000
        }.get(length, 600)

    def _count_words(self, text):
        """Count words in text"""
        return len(text.split())

    def _generate_title(self, text):
        """Generate a meaningful title from the transcript"""
        try:

            sentences = re.split(r'[.!?]+', text)
            if sentences and sentences[0]:
                first_sentence = sentences[0].strip()
                if len(first_sentence) > 100:
                    first_sentence = first_sentence[:97] + "..."
                return first_sentence
            return "Meeting Summary"
        except:
            return "Meeting Summary"

    def _structure_summary(self, summary_text, summary_type):
        """Structure the summary with proper sections"""

        lines = summary_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = re.sub(r'[^\x00-\x7F]+', '', line)
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def summarize_document(self, file_path, summary_type="executive", length="medium"):
        """Summarize a document file"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            text = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise ValueError("Could not read file with any supported encoding")
                
            return self.summarize(text, summary_type, length)
        except Exception as e:
            logger.error(f"Document summarization failed: {str(e)}")
            return {"success": False, "error": str(e)}