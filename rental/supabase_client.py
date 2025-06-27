from supabase import create_client, Client
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            try:
                self._client = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_SERVICE_ROLE_KEY
                )
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {str(e)}")
                self._client = None

    @property
    def client(self) -> Client:
        if self._client is None:
            raise Exception("Supabase client not initialized")
        return self._client

    def get_public_client(self) -> Client:
        """Get client with anon key for public operations"""
        try:
            return create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_ANON_KEY
            )
        except Exception as e:
            logger.error(f"Failed to create public Supabase client: {str(e)}")
            raise

# Singleton instance
supabase_client = SupabaseClient()

def get_supabase_client() -> Client:
    """Get the Supabase client instance"""
    return supabase_client.client

def get_public_supabase_client() -> Client:
    """Get public Supabase client for authentication"""
    return supabase_client.get_public_client()