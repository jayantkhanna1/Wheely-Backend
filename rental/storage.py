import os
import uuid
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from .supabase_client import get_supabase_client
import logging

logger = logging.getLogger(__name__)

class SupabaseStorage(Storage):
    """Custom storage backend for Supabase Storage"""
    
    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'wheely-uploads')
        self.supabase = get_supabase_client()
    
    def _save(self, name, content):
        """Save file to Supabase Storage"""
        try:
            # Generate unique filename if needed
            if self.exists(name):
                name = self._get_unique_name(name)
            
            # Read content
            if hasattr(content, 'read'):
                file_content = content.read()
            else:
                file_content = content
            
            # Upload to Supabase Storage
            response = self.supabase.storage.from_(self.bucket_name).upload(
                path=name,
                file=file_content,
                file_options={"content-type": self._get_content_type(name)}
            )
            
            if response.status_code == 200:
                logger.info(f"File uploaded successfully: {name}")
                return name
            else:
                logger.error(f"Failed to upload file: {response}")
                raise Exception(f"Upload failed: {response}")
                
        except Exception as e:
            logger.error(f"Error uploading file to Supabase: {str(e)}")
            raise
    
    def _open(self, name, mode='rb'):
        """Open file from Supabase Storage"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).download(name)
            return ContentFile(response)
        except Exception as e:
            logger.error(f"Error opening file from Supabase: {str(e)}")
            raise
    
    def delete(self, name):
        """Delete file from Supabase Storage"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).remove([name])
            if response:
                logger.info(f"File deleted successfully: {name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from Supabase: {str(e)}")
            return False
    
    def exists(self, name):
        """Check if file exists in Supabase Storage"""
        try:
            files = self.supabase.storage.from_(self.bucket_name).list()
            return any(file['name'] == name for file in files)
        except Exception as e:
            logger.error(f"Error checking file existence: {str(e)}")
            return False
    
    def listdir(self, path):
        """List directory contents"""
        try:
            files = self.supabase.storage.from_(self.bucket_name).list(path)
            directories = []
            filenames = []
            
            for item in files:
                if item.get('metadata', {}).get('mimetype') == 'application/x-directory':
                    directories.append(item['name'])
                else:
                    filenames.append(item['name'])
            
            return directories, filenames
        except Exception as e:
            logger.error(f"Error listing directory: {str(e)}")
            return [], []
    
    def size(self, name):
        """Get file size"""
        try:
            files = self.supabase.storage.from_(self.bucket_name).list()
            for file in files:
                if file['name'] == name:
                    return file.get('metadata', {}).get('size', 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting file size: {str(e)}")
            return 0
    
    def url(self, name):
        """Get public URL for file"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).get_public_url(name)
            return response
        except Exception as e:
            logger.error(f"Error getting file URL: {str(e)}")
            return None
    
    def _get_unique_name(self, name):
        """Generate unique filename"""
        base, ext = os.path.splitext(name)
        unique_id = str(uuid.uuid4())[:8]
        return f"{base}_{unique_id}{ext}"
    
    def _get_content_type(self, name):
        """Get content type based on file extension"""
        ext = os.path.splitext(name)[1].lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }
        return content_types.get(ext, 'application/octet-stream')