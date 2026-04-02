import os
import json
from supabase import create_client, Client
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SupabaseStorage:
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL')
        self.key = os.environ.get('SUPABASE_ANON_KEY')
        
        if not self.url or not self.key:
            logger.warning("Supabase credentials not set. Using local storage fallback.")
            self.enabled = False
            return
        
        try:
            self.supabase: Client = create_client(self.url, self.key)
            self.bucket_name = 'audio-files'
            self.enabled = True
            self._ensure_bucket()
            logger.info("✅ SupabaseStorage initialized")
        except Exception as e:
            logger.error(f"Supabase initialization error: {str(e)}")
            self.enabled = False
    
    def _ensure_bucket(self):
        """Create bucket if it doesn't exist"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_names = [b['name'] for b in buckets]
            
            if self.bucket_name not in bucket_names:
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={
                        'public': False,
                        'file_size_limit': 104857600,  
                        'allowed_mime_types': ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'application/json']
                    }
                )
                logger.info(f"✅ Created bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Bucket error (non-critical): {str(e)}")
    
    def upload_audio(self, file_data, filename, user_id):
        """Upload audio file to Supabase"""
        if not self.enabled:
            return self._local_fallback(file_data, filename), None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = filename.replace(' ', '_').replace('/', '_')
            path = f"audio/{user_id}/{timestamp}_{safe_filename}"
            
            if len(file_data) > 50 * 1024 * 1024:  
                logger.warning(f"File too large for Supabase: {len(file_data)} bytes. Using local fallback.")
                return self._local_fallback(file_data, filename), None
            
            self.supabase.storage.from_(self.bucket_name).upload(
                path=path,
                file=file_data,
                file_options={"content-type": "audio/mpeg"}
            )
            
            public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(path)
            
            logger.info(f"✅ Audio uploaded: {path}")
            return path, public_url
            
        except Exception as e:
            logger.error(f"❌ Upload failed: {str(e)}. Using local fallback.")
            return self._local_fallback(file_data, filename), None
    
    def upload_transcript(self, transcript_data, filename, user_id):
        """Upload transcript JSON to Supabase"""
        if not self.enabled:
            return None, None
        
        try:
            file_data = json.dumps(transcript_data, indent=2).encode('utf-8')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = filename.rsplit('.', 1)[0]
            path = f"transcripts/{user_id}/{timestamp}_{base_name}.json"
            
            self.supabase.storage.from_(self.bucket_name).upload(
                path=path,
                file=file_data,
                file_options={"content-type": "application/json"}
            )
            
            public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(path)
            
            logger.info(f"✅ Transcript uploaded: {path}")
            return path, public_url
            
        except Exception as e:
            logger.error(f"❌ Transcript upload failed: {str(e)}")
            return None, None
    
    def get_download_url(self, path):
        """Get public URL for file"""
        if not self.enabled or not path:
            return None
        
        try:
            return self.supabase.storage.from_(self.bucket_name).get_public_url(path)
        except Exception as e:
            logger.error(f"❌ URL generation failed: {str(e)}")
            return None
    
    def delete_file(self, path):
        """Delete file from Supabase"""
        if not self.enabled or not path:
            return False
        
        try:
            self.supabase.storage.from_(self.bucket_name).remove([path])
            logger.info(f"✅ File deleted: {path}")
            return True
        except Exception as e:
            logger.error(f"❌ Delete failed: {str(e)}")
            return False
    
    def _local_fallback(self, file_data, filename):
        """Fallback to local storage"""
        from config import Config
        
        upload_dir = os.path.join(Config.BASE_DIR, 'uploads', 'fallback')
        os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = filename.replace(' ', '_').replace('/', '_')
        local_path = os.path.join(upload_dir, f"{timestamp}_{safe_filename}")
        
        with open(local_path, 'wb') as f:
            f.write(file_data)
        
        logger.warning(f"⚠ Using local fallback: {local_path}")
        return local_path

supabase_storage = SupabaseStorage()