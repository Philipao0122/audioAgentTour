import os
import streamlit as st
from supabase import create_client, Client
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class SupabaseManager:
    """Clase para gestionar todas las interacciones con la base de datos Supabase."""

    def __init__(self):
        """Inicializa el cliente de Supabase."""
        self.client = self._init_supabase()

    def _init_supabase(self) -> Optional[Client]:
        """Inicializa y retorna el cliente de Supabase."""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            st.error("❌ URL o clave de Supabase no configurada. Contacta al administrador.")
            logger.error("Variables de entorno de Supabase no configuradas.")
            st.stop()
            return None
        
        try:
            return create_client(url, key)
        except Exception as e:
            st.error(f"❌ Error al conectar con Supabase: {e}")
            logger.error(f"Error al crear el cliente de Supabase: {e}")
            st.stop()
            return None
            
    # ==========================
    # Authentication Methods
    # ==========================
    def check_email_in_whitelist(self, email: str) -> Dict[str, Any]:
        """
        Verifica el estado de un correo en la tabla whitelist_users.
        
        Returns:
            Dict con las claves:
            - exists: bool - Si el correo existe en la tabla
            - is_active: bool - Si la cuenta está activa
            - role: str - Rol del usuario (si existe)
        """
        if not self.client or not email:
            return {"exists": False, "is_active": False, "role": "user"}
            
        try:
            # Verificar en la tabla whitelist_users
            result = self.client.table("whitelist_users") \
                             .select("is_active, role") \
                             .eq("email", email) \
                             .maybe_single() \
                             .execute()
            
            if not result.data:
                return {"exists": False, "is_active": False, "role": "user"}
                
            # El correo existe, devolvemos su estado actual
            return {
                "exists": True,
                "is_active": bool(result.data.get('is_active')),
                "role": result.data.get('role', 'user')
            }
            
        except Exception as e:
            logger.error(f"Error al verificar whitelist_users: {e}")
            return {"exists": False, "is_active": False, "role": "user"}
            
    def is_admin(self, email: str) -> bool:
        """Verifica si el usuario es administrador."""
        if not self.client or not email:
            return False
            
        try:
            result = self.client.table("whitelist_users") \
                             .select("role") \
                             .eq("email", email) \
                             .maybe_single() \
                             .execute()
            
            return result.data and result.data.get('role') == 'admin'
            
        except Exception as e:
            logger.error(f"Error al verificar rol de administrador: {e}")
            return False
            
    def get_all_whitelist_emails(self) -> List[Dict[str, Any]]:
        """Obtiene todos los correos electrónicos de la lista blanca."""
        if not self.client:
            return []
            
        try:
            result = self.client.table("whitelist_users") \
                             .select("email, role, is_active, created_at") \
                             .order("created_at", desc=True) \
                             .execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error al obtener la lista blanca: {e}")
            return []
            
    def request_access(self, email: str) -> Dict[str, Any]:
        """
        Crea o actualiza una solicitud de acceso para el correo electrónico.
        
        Returns:
            Dict con las claves:
            - success: bool - Si la operación fue exitosa
            - message: str - Mensaje descriptivo del resultado
            - status: str - Estado actual de la cuenta ('pending', 'active', 'error')
        """
        # Respuesta por defecto en caso de error
        error_response = {
            "success": False, 
            "message": "Error al procesar la solicitud. Por favor, inténtalo de nuevo más tarde.",
            "status": "error"
        }
        
        if not self.client or not email:
            error_response["message"] = "Error de configuración del sistema"
            return error_response
            
        try:
            # Verificar el estado actual del correo
            current_status = self.check_email_in_whitelist(email)
            
            # Si el correo ya existe
            if current_status["exists"]:
                if current_status["is_active"]:
                    return {
                        "success": True,
                        "message": "Esta cuenta ya está activa",
                        "status": "active"
                    }
                else:
                    return {
                        "success": True,
                        "message": "Ya tienes una solicitud pendiente de aprobación. Te notificaremos cuando sea revisada.",
                        "status": "pending"
                    }
            
            # Si el correo no existe, crear nueva solicitud
            result = self.client.table("whitelist_users").insert({
                "email": email,
                "role": "user",
                "is_active": False,
                "created_at": datetime.now().isoformat(),
                "tokens_used": 0,
                "token_limit": 10000,  # Límite por defecto
                "updated_at": datetime.now().isoformat()
            }).execute()
            
            # Verificar si la inserción fue exitosa
            if not result.data:
                error_response["message"] = "No se pudo crear la solicitud. Inténtalo de nuevo."
                return error_response
            
            return {
                "success": True,
                "message": "✅ Solicitud de acceso creada correctamente. Un administrador la revisará pronto.",
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Error al crear solicitud de acceso: {e}")
            error_response["message"] = f"Error en el servidor: {str(e)}"
            return error_response
            
    def approve_user(self, email: str) -> Dict[str, Any]:
        """
        Aprueba una solicitud de acceso.
        
        Returns:
            Dict con las claves:
            - success: bool - Si la operación fue exitosa
            - message: str - Mensaje descriptivo del resultado
            - user: Optional[Dict] - Datos del usuario actualizados
        """
        if not self.client or not email:
            return {
                "success": False,
                "message": "Parámetros inválidos",
                "user": None
            }
            
        try:
            # Verificar si el usuario existe
            current_status = self.check_email_in_whitelist(email)
            
            if not current_status["exists"]:
                return {
                    "success": False,
                    "message": "El usuario no existe",
                    "user": None
                }
                
            if current_status["is_active"]:
                return {
                    "success": True,
                    "message": "El usuario ya está activo",
                    "user": {"email": email, "is_active": True, "role": current_status["role"]}
                }
            
            # Actualizar el estado a activo
            result = self.client.table("whitelist_users") \
                             .update({
                                 "is_active": True,
                                 "updated_at": datetime.now().isoformat()
                             }) \
                             .eq("email", email) \
                             .execute()
            
            if not result.data:
                return {
                    "success": False,
                    "message": "No se pudo actualizar el usuario",
                    "user": None
                }
                
            return {
                "success": True,
                "message": "Usuario aprobado exitosamente",
                "user": result.data[0] if result.data else None
            }
            
        except Exception as e:
            logger.error(f"Error al aprobar usuario {email}: {e}")
            return False
            
    def add_email_to_whitelist(self, email: str, role: str = 'user') -> bool:
        """Agrega un email a la lista blanca."""
        if not self.client or not email:
            return False
            
        try:
            self.client.table("whitelist_users").upsert({
                "email": email,
                "role": role,
                "is_active": True,
                "created_at": "now()"
            }).execute()
            return True
            
        except Exception as e:
            logger.error(f"Error al agregar email a la lista blanca: {e}")
            return False
            
    def remove_email_from_whitelist(self, email: str) -> bool:
        """Elimina un email de la lista blanca."""
        if not self.client or not email:
            return False
            
        try:
            self.client.table("whitelist_users") \
                     .delete() \
                     .eq("email", email) \
                     .execute()
            return True
            
        except Exception as e:
            logger.error(f"Error al eliminar email de la lista blanca: {e}")
            return False
            
    def add_to_whitelist(self, email: str, is_admin: bool = False) -> bool:
        """Agrega un correo a la lista blanca."""
        if not self.client:
            return False
            
        try:
            self.client.table("whitelist").upsert({
                "email": email,
                "is_approved": True,
                "is_admin": is_admin,
                "added_at": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Error al agregar a lista blanca: {e}")
            return False
            
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """
        Obtiene las solicitudes pendientes de aprobación.
        
        Returns:
            Lista de diccionarios con información de las solicitudes pendientes
        """
        if not self.client:
            return []
            
        try:
            result = self.client.table("whitelist_users") \
                             .select("email, created_at, role") \
                             .eq("is_active", False) \
                             .order("created_at", desc=True) \
                             .execute()
            
            # Asegurarse de que los datos tengan el formato correcto
            pending_approvals = []
            for item in (result.data or []):
                pending_approvals.append({
                    "email": item.get("email", ""),
                    "created_at": item.get("created_at", ""),
                    "role": item.get("role", "user")
                })
                
            return pending_approvals
            
        except Exception as e:
            logger.error(f"Error al obtener aprobaciones pendientes: {e}")
            return []
            
    def reject_user(self, email: str) -> bool:
        """Rechaza una solicitud de acceso."""
        return self.remove_email_from_whitelist(email)
            
    def update_user_role(self, email: str, role: str) -> bool:
        """Actualiza el rol de un usuario."""
        if not self.client or not email or not role:
            return False
            
        try:
            result = self.client.table("whitelist_users") \
                             .update({"role": role}) \
                             .eq("email", email) \
                             .execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error al actualizar el rol del usuario {email}: {e}")
            return False
            
    def remove_from_whitelist(self, email: str) -> bool:
        """Elimina un correo de la lista blanca."""
        if not self.client:
            return False
            
        try:
            self.client.table("whitelist") \
                     .delete() \
                     .eq("email", email) \
                     .execute()
            return True
        except Exception as e:
            logger.error(f"Error al eliminar de lista blanca: {e}")
            return False

    # ==========================
    # Token Management
    # ==========================
    def check_token_usage(self, email: str, required_tokens: int = 0) -> Dict[str, Any]:
        """Verifica si el usuario puede usar más tokens."""
        if not self.client or not email:
            return {"can_proceed": False, "reason": "Error de autenticación"}
            
        try:
            # Verificar si el usuario es administrador
            if self.is_admin(email):
                return {
                    "can_proceed": True,
                    "tokens_used": 0,
                    "tokens_limit": float('inf'),
                    "is_admin": True,
                    "message": "Admin sin restricciones"
                }
                
            # Obtener información de tokens del usuario
            result = self.client.table("whitelist_users") \
                             .select("tokens_used, token_limit") \
                             .eq("email", email) \
                             .maybe_single() \
                             .execute()
            
            if not result.data:
                return {"can_proceed": False, "reason": "Usuario no encontrado"}
                
            tokens_used = result.data.get('tokens_used', 0) or 0
            token_limit = result.data.get('token_limit', 10000) or 10000  # Límite predeterminado: 10,000 tokens
            
            # Si el límite es 0, es ilimitado
            if token_limit == 0:
                token_limit = float('inf')
            
            # Verificar si puede usar más tokens
            can_proceed = (tokens_used + required_tokens) <= token_limit
            
            return {
                "can_proceed": can_proceed,
                "tokens_used": tokens_used,
                "tokens_limit": token_limit,
                "is_admin": False,
                "message": f"Usados: {tokens_used}/{token_limit}" if token_limit != float('inf') else "Uso ilimitado"
            }
            
        except Exception as e:
            logger.error(f"Error al verificar uso de tokens: {e}")
            # En caso de error, permitir el acceso pero registrar el error
            return {
                "can_proceed": True,
                "tokens_used": 0,
                "tokens_limit": float('inf'),
                "is_admin": False,
                "message": "Error al verificar tokens, acceso permitido"
            }

    def update_token_usage(self, email: str, tokens_used: int) -> bool:
        """Actualiza el contador de tokens usados por un usuario."""
        # No actualizar tokens para administradores
        if self.is_admin(email):
            return True
            
        if not self.client or not email:
            return False
            
        try:
            # Obtener el conteo actual de tokens
            result = self.client.table("whitelist_users") \
                             .select("tokens_used") \
                             .eq("email", email) \
                             .maybe_single() \
                             .execute()
            
            if not result.data:
                return False
                
            current_tokens = result.data.get('tokens_used', 0) or 0
            new_tokens = current_tokens + tokens_used
            
            # Actualizar el contador de tokens
            self.client.table("whitelist_users") \
                     .update({"tokens_used": new_tokens}) \
                     .eq("email", email) \
                     .execute()
                     
            return True
            
        except Exception as e:
            logger.error(f"Error al actualizar uso de tokens: {e}")
            # En caso de error, permitir la operación pero registrar el error
            return True

    def get_all_token_usage(self) -> List[Dict[str, Any]]:
        """Obtiene el uso de tokens de todos los usuarios (solo para administradores)."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("user_token_usage") \
                             .select("*") \
                             .order("user_email") \
                             .execute()
            return result.data
        except Exception as e:
            logger.error(f"Error al obtener el uso de tokens: {e}")
            return []

    def update_token_limit(self, email: str, new_limit: int) -> bool:
        """Actualiza el límite de tokens para un usuario."""
        if not self.client:
            return False
            
        try:
            self.client.table("user_token_usage") \
                     .upsert({
                         "user_email": email,
                         "tokens_limit": new_limit
                     }) \
                     .execute()
            return True
        except Exception as e:
            logger.error(f"Error al actualizar el límite de tokens: {e}")
            return False

    def reset_token_usage(self, email: str) -> bool:
        """Reinicia el contador de tokens para un usuario."""
        if not self.client:
            return False
            
        try:
            self.client.table("user_token_usage") \
                     .update({"tokens_used": 0}) \
                     .eq("user_email", email) \
                     .execute()
            return True
        except Exception as e:
            logger.error(f"Error al reiniciar el contador de tokens: {e}")
            return False