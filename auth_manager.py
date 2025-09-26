import streamlit as st
from supabase_manager import SupabaseManager
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    """Gestor de autenticación y autorización."""

    def __init__(self):
        self.supabase = SupabaseManager()

    def show_login_form(self) -> Optional[str]:
        """
        Muestra el formulario de login y maneja el flujo de solicitud de acceso.
        
        Returns:
            str: Email del usuario si el inicio de sesión es exitoso
            None: Si hay un error o la sesión no se puede iniciar
        """
        st.title("🔐 Acceso al Audio Tour Generator")
        st.write("Por favor, ingresa tu email para acceder al servicio.")

        with st.form("login_form"):
            email = st.text_input(
                "📧 Email",
                placeholder="tu.email@ejemplo.com",
                help="Ingresa tu email para verificar acceso"
            )

            submitted = st.form_submit_button("🔓 Acceder", use_container_width=True)

            if submitted:
                if not email:
                    st.error("❌ Por favor ingresa tu email")
                    return None

                if not self._is_valid_email(email):
                    st.error("❌ Por favor ingresa un email válido")
                    return None

                # Verificar el estado del correo en la lista blanca
                user_status = self.supabase.check_email_in_whitelist(email)
                
                # Si el usuario existe y está activo, permitir acceso
                if user_status["exists"] and user_status["is_active"]:
                    st.success(f"✅ ¡Bienvenido {email}! Redirigiendo...")
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.session_state.is_admin = (user_status.get("role") == "admin")
                    st.rerun()
                    return email
                
                # Si el usuario existe pero está inactivo (pendiente de aprobación)
                elif user_status["exists"] and not user_status["is_active"]:
                    st.warning("⏳ Tu cuenta está pendiente de aprobación. Te notificaremos por correo cuando tu acceso sea aprobado.")
                    return None
                
                # Si el usuario no existe, crear una nueva solicitud
                else:
                    st.info("📨 No estás en la lista de acceso. Creando una solicitud...")
                    request_result = self.supabase.request_access(email)
                    
                    # Manejar diferentes tipos de respuesta
                    if isinstance(request_result, dict):
                        if request_result.get("success"):
                            if request_result.get("status") == "pending":
                                st.success("✅ " + request_result.get("message", "Solicitud enviada correctamente."))
                            elif request_result.get("status") == "active":
                                st.success("✅ " + request_result.get("message", "Tu cuenta ya está activa."))
                            else:
                                st.success("✅ " + request_result.get("message", "Solicitud procesada correctamente."))
                        else:
                            error_msg = request_result.get("message", "Error al procesar tu solicitud. Intenta nuevamente.")
                            st.error(f"❌ {error_msg}")
                    else:
                        # Manejar el caso en que request_result es un booleano
                        if request_result:
                            st.success("✅ Solicitud procesada correctamente.")
                        else:
                            st.error("❌ Error al procesar tu solicitud. Por favor, inténtalo de nuevo o contacta al administrador.")
                    
                    return None

        return None
    def show_admin_panel(self):
        """Muestra el panel de administración para gestionar la whitelist."""
        st.title("👨‍💼 Panel de Administración")

        tab1, tab2, tab3, tab4 = st.tabs([
            "👥 Ver Usuarios", 
            "➕ Agregar Usuario", 
            "⏳ Solicitudes Pendientes",
            "🗑️ Remover Usuario"
        ])

        with tab1:
            st.subheader("Usuarios Autorizados")
            users = self.supabase.get_all_whitelist_emails()

            if users:
                # Pre-procesar los datos para el dataframe
                display_users = []
                for user in users:
                    display_users.append({
                        "📧 Email": user.get("email", ""),
                        "👤 Rol": "Administrador" if user.get("role") == "admin" else "Usuario",
                        "✅ Activo": "Sí" if user.get("is_active") else "No"
                    })
                
                st.dataframe(
                    display_users,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Opción para eliminar usuarios
                with st.expander("❌ Eliminar Usuario"):
                    email_to_remove = st.selectbox(
                        "Selecciona un email para eliminar",
                        [""] + [user["📧 Email"] for user in display_users],
                        format_func=lambda x: x if x else "Selecciona un email"
                    )
                    
                    if st.button("Eliminar Usuario", type="primary", use_container_width=True):
                        if email_to_remove:
                            if self.supabase.remove_email_from_whitelist(email_to_remove):
                                st.success(f"✅ {email_to_remove} eliminado exitosamente")
                                st.rerun()
                            else:
                                st.error(f"❌ Error al eliminar {email_to_remove}")
                        else:
                            st.warning("Por favor ingresa un email para eliminar")
            else:
                st.info("ℹ️ No hay usuarios autorizados")

        with tab2:
            st.subheader("Agregar Nuevo Usuario")
            with st.form("add_user_form"):
                new_email = st.text_input("📧 Email del nuevo usuario")
                role = st.selectbox(
                    "👤 Rol", 
                    ["user", "admin"], 
                    format_func=lambda x: "Usuario" if x == "user" else "Administrador"
                )
                
                submitted = st.form_submit_button("➕ Agregar Usuario", type="primary", use_container_width=True)

                if submitted:
                    if not new_email:
                        st.error("❌ Por favor ingresa un email")
                    elif not self._is_valid_email(new_email):
                        st.error("❌ Por favor ingresa un email válido")
                    else:
                        if self.supabase.add_email_to_whitelist(new_email, role):
                            st.success(f"✅ {new_email} agregado exitosamente como {'Administrador' if role == 'admin' else 'Usuario'}")
                            st.rerun()
                        else:
                            st.error(f"❌ Error al agregar {new_email}")

        with tab3:
            st.subheader("Solicitudes de Acceso Pendientes")
            pending_users = self.supabase.get_pending_approvals()

            if not pending_users:
                st.info("ℹ️ No hay solicitudes pendientes.")
            else:
                for user in pending_users:
                    email = user['email']
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"📧 {email}")
                    with col2:
                        if st.button("✅ Aceptar", key=f"approve_{email}", use_container_width=True):
                            if self.supabase.approve_user(email):
                                st.success(f"✅ {email} ha sido aprobado.")
                                st.rerun()
                            else:
                                st.error(f"❌ Error al aprobar a {email}.")
                    with col3:
                        if st.button("❌ Rechazar", key=f"reject_{email}", use_container_width=True):
                            if self.supabase.reject_user(email):
                                st.success(f"🗑️ Solicitud de {email} rechazada.")
                                st.rerun()
                            else:
                                st.error(f"❌ Error al rechazar a {email}.")

        with tab4:
            st.subheader("Remover Usuario")
            users = self.supabase.get_all_whitelist_emails()
            
            if users and isinstance(users, list):
                # Extraer solo los correos electrónicos para el selectbox
                email_list = [user.get('email', '') for user in users if user.get('email')]
                
                if email_list:
                    email_to_remove = st.selectbox(
                        "Seleccionar email a remover",
                        [""] + email_list,
                        format_func=lambda x: x if x else "Selecciona un email"
                    )
                    
                    if email_to_remove and st.button("🗑️ Remover Usuario Seleccionado", type="primary", use_container_width=True):
                        if self.supabase.remove_email_from_whitelist(email_to_remove):
                            st.success(f"✅ {email_to_remove} removido exitosamente")
                            st.rerun()
                        else:
                            st.error(f"❌ Error al remover {email_to_remove}")
                else:
                    st.info("ℹ️ No hay usuarios para remover")
            else:
                st.info("ℹ️ No hay usuarios para remover")

    def _is_valid_email(self, email: str) -> bool:
        """Valida el formato de un email."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def logout(self):
        """Cierra la sesión del usuario."""
        if 'authenticated' in st.session_state:
            del st.session_state.authenticated
        if 'user_email' in st.session_state:
            del st.session_state.user_email
        st.rerun()
