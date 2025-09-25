import os
import streamlit as st
from supabase import create_client, Client
import logging
from typing import List, Optional
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

class SupabaseManager:
    """Manages all interactions with the Supabase backend."""

    def __init__(self):
        self.client = self._init_supabase()

    def _init_supabase(self) -> Optional[Client]:
        """Initializes and returns the Supabase client."""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            st.error("❌ Supabase URL or Key not configured. Contact the administrator.")
            logger.error("Supabase environment variables not set.")
            st.stop()
            return None
        
        try:
            return create_client(url, key)
        except Exception as e:
            st.error(f"❌ Error connecting to Supabase: {e}")
            logger.error(f"Failed to create Supabase client: {e}")
            st.stop()
            return None

    def check_email_in_whitelist(self, email: str) -> Optional[dict]:
        """Checks if an email exists and returns its status, or None if not found."""
        if not self.client:
            return False
        try:
            result = self.client.table("whitelist_users").select("is_active").eq("email", email).execute()
            if result.data:
                return result.data[0]  # Returns {'is_active': True/False}
            return None
        except Exception as e:
            logger.error(f"Error checking whitelist for {email}: {e}")
            st.error("❌ An error occurred while verifying your access.")
            return None

    def is_admin(self, email: str) -> bool:
        """Checks if a user has the 'admin' role."""
        if not self.client:
            return False
        try:
            result = self.client.table("whitelist_users").select("role").eq("email", email).execute()
            if result.data and result.data[0].get('role') == 'admin':
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking admin status for {email}: {e}")
            return False

    def get_all_whitelist_emails(self) -> List[str]:
        """Retrieves all emails from the whitelist."""
        if not self.client:
            return []
        try:
            result = self.client.table("whitelist_users").select("email").order("email").execute()
            return [item['email'] for item in result.data]
        except Exception as e:
            logger.error(f"Error fetching all whitelist emails: {e}")
            return []

    def add_email_to_whitelist(self, email: str, role: str = 'user') -> bool:
        """Adds a new email to the whitelist."""
        if not self.client:
            return False
        try:
            # First, check if the email already exists to prevent duplicates
            existing = self.client.table("whitelist_users").select("id").eq("email", email).execute()
            if existing.data:
                st.warning(f"⚠️ Email {email} already exists in the whitelist.")
                return False

            self.client.table("whitelist_users").insert({"email": email, "role": role, "is_active": True}).execute()
            logger.info(f"Email {email} with role {role} added to whitelist.")
            return True
        except Exception as e:
            logger.error(f"Error adding {email} to whitelist: {e}")
            return False

    def request_access(self, email: str) -> bool:
        """Adds a new user with is_active=False to request access."""
        if not self.client:
            return False
        try:
            self.client.table("whitelist_users").insert({"email": email, "is_active": False, "role": "user"}).execute()
            logger.info(f"Access request for {email} created.")
            return True
        except Exception as e:
            # Handles cases where the email already exists (unique constraint)
            logger.error(f"Error creating access request for {email}: {e}")
            return False

    def get_pending_users(self) -> List[dict]:
        """Retrieves all users with is_active=False."""
        if not self.client:
            return []
        try:
            result = self.client.table("whitelist_users").select("email").eq("is_active", False).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error fetching pending users: {e}")
            return []

    def approve_user(self, email: str) -> bool:
        """Approves a user by setting is_active=True."""
        if not self.client:
            return False
        try:
            self.client.table("whitelist_users").update({"is_active": True, "role": "user"}).eq("email", email).execute()
            logger.info(f"User {email} approved.")
            return True
        except Exception as e:
            logger.error(f"Error approving user {email}: {e}")
            return False

    def reject_user(self, email: str) -> bool:
        """Rejects a user by deleting their record."""
        if not self.client:
            return False
        try:
            self.client.table("whitelist_users").delete().eq("email", email).execute()
            logger.info(f"User {email} rejected and removed.")
            return True
        except Exception as e:
            logger.error(f"Error rejecting user {email}: {e}")
            return False

    def remove_email_from_whitelist(self, email: str) -> bool:
        """Removes an email from the whitelist."""
        if not self.client:
            return False
        try:
            self.client.table("whitelist_users").delete().eq("email", email).execute()
            logger.info(f"Email {email} removed from whitelist.")
            return True
        except Exception as e:
            logger.error(f"Error removing {email} from whitelist: {e}")
            return False

    # ==========================
    # Usage & Quota Management
    # ==========================
    def _current_month_key(self) -> str:
        """Returns the current month key in YYYY-MM format."""
        return datetime.utcnow().strftime("%Y-%m")

    def _get_limits(self) -> Tuple[int, int]:
        """Fetch default monthly limits from env. Returns (token_limit, tts_char_limit)."""
        token_limit = int(os.getenv("MONTHLY_TOKEN_LIMIT", "10000"))   # 100k tokens default
        tts_limit = int(os.getenv("MONTHLY_TTS_CHAR_LIMIT", "100000"))  # 300k chars default
        return token_limit, tts_limit

    def ensure_usage_row(self, email: str) -> Optional[dict]:
        """Ensures there is a usage row for the current month; returns the row."""
        if not self.client:
            return None
        month = self._current_month_key()
        try:
            result = (
                self.client
                .table("user_usage")
                .select("email, month, tokens_used, tts_chars_used")
                .eq("email", email)
                .eq("month", month)
                .execute()
            )
            if result.data:
                return result.data[0]

            insert = (
                self.client
                .table("user_usage")
                .insert({
                    "email": email,
                    "month": month,
                    "tokens_used": 0,
                    "tts_chars_used": 0,
                })
                .execute()
            )
            return insert.data[0] if insert.data else {
                "email": email, "month": month, "tokens_used": 0, "tts_chars_used": 0
            }
        except Exception as e:
            logger.error(f"Error ensuring usage row for {email}: {e}")
            return None

    def get_usage_status(self, email: str) -> Optional[dict]:
        """Returns current usage and limits for the user for this month."""
        row = self.ensure_usage_row(email)
        if row is None:
            return None
        token_limit, tts_limit = self._get_limits()
        return {
            "email": email,
            "month": row.get("month"),
            "tokens_used": row.get("tokens_used", 0),
            "tts_chars_used": row.get("tts_chars_used", 0),
            "token_limit": token_limit,
            "tts_char_limit": tts_limit,
            "tokens_remaining": max(0, token_limit - row.get("tokens_used", 0)),
            "tts_chars_remaining": max(0, tts_limit - row.get("tts_chars_used", 0)),
        }

    def can_consume(self, email: str, tokens_needed: int = 0, tts_chars_needed: int = 0):
        """Checks if the user can consume the requested amounts."""
        status = self.get_usage_status(email)
        if status is None:
            return False, {"reason": "usage_unavailable"}
        ok = (
            status["tokens_remaining"] >= tokens_needed and
            status["tts_chars_remaining"] >= tts_chars_needed
        )
        return ok, status

    def add_usage(self, email: str, tokens_used: int = 0, tts_chars_used: int = 0) -> bool:
        """Adds actual usage to the current month. Uses RPC if present; otherwise falls back."""
        if not self.client:
            return False
        month = self._current_month_key()
        try:
            # Ensure row exists first
            self.ensure_usage_row(email)
            # Try RPC for atomic increment
            try:
                self.client.rpc(
                    "increment_usage",
                    {"p_email": email, "p_month": month, "p_tokens": tokens_used, "p_tts_chars": tts_chars_used}
                ).execute()
                return True
            except Exception:
                # Fallback simple update
                current = (
                    self.client.table("user_usage").select("tokens_used, tts_chars_used")
                    .eq("email", email).eq("month", month).execute()
                )
                if current.data:
                    new_tokens = int(current.data[0].get("tokens_used", 0)) + int(tokens_used)
                    new_tts = int(current.data[0].get("tts_chars_used", 0)) + int(tts_chars_used)
                    self.client.table("user_usage").update({
                        "tokens_used": new_tokens,
                        "tts_chars_used": new_tts,
                    }).eq("email", email).eq("month", month).execute()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error adding usage for {email}: {e}")
            return False
