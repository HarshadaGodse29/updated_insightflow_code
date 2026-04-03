import os
import json
import time
import logging
import threading
import queue
import numpy as np
import sounddevice as sd
from datetime import datetime
import websocket
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
STREAM_URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"


class LiveTranscriptionModule:
    def __init__(self):
        if not ASSEMBLYAI_API_KEY:
            raise ValueError("ASSEMBLYAI_API_KEY not found in environment variables")

        self.api_key = ASSEMBLYAI_API_KEY
        self.ws = None
        self.ws_thread = None
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.is_connected = False
        self.partial_text = ""
        self.final_transcripts = []
        self.current_speaker = "Speaker A"
        self.detected_language = "auto"
        self.language_name = "Detecting..."
        self.session_id = None
        self.start_time = None
        self.word_count = 0
        
        self.sample_rate = 16000
        self.channels = 1
        self.blocksize = 4096
        self.device = None
        self.stream = None
        
        self.on_partial = None
        self.on_final = None
        self.on_error = None
        
        logger.info("LiveTranscriptionModule initialized")

    def list_audio_devices(self):
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'default_samplerate': device['default_samplerate']
                    })
            return input_devices
        except Exception as e:
            logger.error(f"Error listing devices: {str(e)}")
            return []

    def start_session(self, session_id=None, language='auto', 
                      on_partial=None, on_final=None, on_error=None,
                      device_index=None):
        self.session_id = session_id or int(time.time())
        self.language = language
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
        self.start_time = time.time()
        self.final_transcripts = []
        self.word_count = 0
        self.partial_text = ""
        
        if device_index is not None:
            self.device = device_index
        
        try:
            self.ws_thread = threading.Thread(target=self._connect_websocket)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            for i in range(20):
                if self.is_connected:
                    break
                time.sleep(0.5)
            
            if not self.is_connected:
                raise Exception("Failed to connect to AssemblyAI")
            
            self._start_audio_capture()
            
            logger.info(f"Live session started: {self.session_id}")
            return self.session_id
            
        except Exception as e:
            logger.error(f"Failed to start session: {str(e)}")
            if self.on_error:
                self.on_error(str(e))
            return None

    def _connect_websocket(self):
        try:
            websocket.enableTrace(False)
            self.ws = websocket.WebSocketApp(
                f"{STREAM_URL}&token={self.api_key}",
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            self.ws.run_forever()
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            self.is_connected = False
            if self.on_error:
                self.on_error(f"Connection error: {str(e)}")

    def _on_open(self, ws):
        logger.info("WebSocket connected to AssemblyAI")
        
        config = {
            "sample_rate": 16000,
            "word_boost": [],
            "encoding": "pcm_s16le",
            "audio": True,
        }
        
        # for multilingual support
        config["model"] = "universal_2"
        
        if self.language and self.language != 'auto':
            config["language_code"] = self.language
        
        ws.send(json.dumps(config))
        self.is_connected = True
        logger.info(f"Configuration sent: {config}")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            message_type = data.get("message_type")
            
            if message_type == "PartialTranscript":
                text = data.get("text", "")
                if text and text.strip():
                    self.partial_text = text
                    if self.on_partial:
                        self.on_partial({
                            'text': text,
                            'speaker': self.current_speaker,
                            'timestamp': datetime.now().isoformat()
                        })
            
            elif message_type == "FinalTranscript":
                text = data.get("text", "")
                if text and text.strip():
                    # Get detected language
                    if "language" in data:
                        self.detected_language = data.get("language", "auto")
                        self.language_name = self._get_language_name(self.detected_language)
                    
                    segment = {
                        'speaker': self.current_speaker,
                        'text': text,
                        'timestamp': datetime.now().isoformat(),
                        'words': len(text.split())
                    }
                    
                    self.final_transcripts.append(segment)
                    self.word_count += len(text.split())
                    
                    if self.on_final:
                        self.on_final(segment)
            
            elif message_type == "SessionInformation":
                if "language" in data:
                    self.detected_language = data.get("language", "auto")
                    self.language_name = self._get_language_name(self.detected_language)
                    logger.info(f"Detected language: {self.language_name}")
            
            elif message_type == "SessionTerminated":
                logger.info("Session terminated")
                self.is_connected = False
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {str(error)}")
        if self.on_error:
            self.on_error(f"WebSocket error: {str(error)}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.is_connected = False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.debug(f"Audio status: {status}")
        
        audio_bytes = indata.tobytes()
        
        if self.is_connected and self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                self.ws.send(audio_bytes, websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                logger.error(f"Error sending audio: {str(e)}")

    def _start_audio_capture(self):
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                blocksize=self.blocksize,
                device=self.device,
                dtype='int16'
            )
            
            self.stream.start()
            self.is_recording = True
            logger.info(f"Audio capture started on device {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {str(e)}")
            self.is_recording = False
            if self.on_error:
                self.on_error(f"Audio capture error: {str(e)}")

    def stop_session(self):
        logger.info("Stopping live session")
        self.is_recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        if self.ws:
            self.ws.close()
            self.ws = None
        
        self.is_connected = False
        
        duration = int(time.time() - self.start_time) if self.start_time else 0
        
        return {
            'session_id': self.session_id,
            'transcript': self.final_transcripts,
            'word_count': self.word_count,
            'duration': duration,
            'speakers': len(set(s['speaker'] for s in self.final_transcripts)) if self.final_transcripts else 0,
            'detected_language': self.detected_language,
            'language_name': self.language_name
        }

    def pause_session(self):
        if self.stream:
            self.stream.stop()
        self.is_recording = False
        logger.info("Session paused")

    def resume_session(self):
        if self.stream:
            self.stream.start()
        self.is_recording = True
        logger.info("Session resumed")

    def switch_speaker(self, speaker_name):
        self.current_speaker = speaker_name
        logger.info(f"Switched to speaker: {speaker_name}")
        
    def get_session_stats(self):
        return {
            'session_id': self.session_id,
            'duration': int(time.time() - self.start_time) if self.start_time else 0,
            'word_count': self.word_count,
            'segments': len(self.final_transcripts),
            'detected_language': self.language_name,
            'current_speaker': self.current_speaker,
            'is_recording': self.is_recording,
            'is_connected': self.is_connected
        }

    def _get_language_name(self, lang_code):
        languages = {
            'hi': 'Hindi', 'mr': 'Marathi', 'ta': 'Tamil', 'te': 'Telugu',
            'bn': 'Bengali', 'gu': 'Gujarati', 'kn': 'Kannada', 'ml': 'Malayalam',
            'pa': 'Punjabi', 'ur': 'Urdu', 'en': 'English', 'es': 'Spanish',
            'fr': 'French', 'de': 'German', 'it': 'Italian', 'pt': 'Portuguese',
            'ru': 'Russian', 'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese',
            'ar': 'Arabic', 'nl': 'Dutch', 'sv': 'Swedish', 'da': 'Danish',
            'auto': 'Auto-detected'
        }
        return languages.get(lang_code, lang_code)


live_transcriber = LiveTranscriptionModule()