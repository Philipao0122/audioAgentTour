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
        """Muestra el formulario de login y retorna el email si es válido."""
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

                user_status = self.supabase.check_email_in_whitelist(email)

                if user_status and user_status.get('is_active'):
                    st.success(f"✅ ¡Bienvenido {email}! Redirigiendo...")
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.rerun()
                elif user_status and not user_status.get('is_active'):
                    st.warning("⏳ Tu solicitud de acceso está pendiente de aprobación.")
                else:
                    # Si el email no existe, se crea la solicitud de acceso automáticamente.
                    st.info("Tu email no está registrado. Creando una solicitud de acceso...")
                    if self.supabase.request_access(email):
                        st.success("✅ ¡Solicitud enviada! Tu acceso ahora está pendiente de aprobación.")
                        import time
                        time.sleep(2) # Pausa para que el usuario lea el mensaje
                        st.rerun()
                    else:
                        st.error("❌ Hubo un error al procesar tu solicitud. Es posible que el email ya esté pendiente.")
                return None

        return None

    def show_admin_panel(self):
        """Muestra el panel de administración para gestionar la whitelist."""
        st.title("⚙️ Panel de Administración")
        st.write("Gestiona los emails autorizados para acceder al servicio.")

        if not self.supabase.is_admin(st.session_state.user_email):
            st.error("❌ No tienes permisos de administrador")
            return

        tab1, tab2, tab3, tab4 = st.tabs(["👥 Ver Usuarios", "➕ Agregar Usuario", "⏳ Solicitudes Pendientes", "❌ Remover Usuario"])

        with tab1:
            st.subheader("Usuarios Autorizados")
            emails = self.supabase.get_all_whitelist_emails()

            if emails:
                for email in emails:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📧 {email}")
                    with col2:
                        if st.button("🗑️ Remover", key=f"remove_{email}"):
                            if self.supabase.remove_email_from_whitelist(email):
                                st.success(f"✅ {email} removido exitosamente")
                                st.rerun()
                            else:
                                st.error(f"❌ Error al remover {email}")
            else:
                st.info("ℹ️ No hay usuarios autorizados")

        with tab2:
            st.subheader("Agregar Nuevo Usuario")
            with st.form("add_user_form"):
                new_email = st.text_input("📧 Email del nuevo usuario")
                role = st.selectbox("👤 Rol", ["user", "admin"], format_func=lambda x: "Usuario" if x == "user" else "Administrador")

                submitted = st.form_submit_button("➕ Agregar Usuario", use_container_width=True)

                if submitted:
                    if not new_email:
                        st.error("❌ Por favor ingresa un email")
                    elif not self._is_valid_email(new_email):
                        st.error("❌ Por favor ingresa un email válido")
                    else:
                        if self.supabase.add_email_to_whitelist(new_email, role):
                            st.success(f"✅ {new_email} agregado exitosamente como {role}")
                            st.rerun()
                        else:
                            st.error(f"❌ Error al agregar {new_email}")

        with tab3:
            st.subheader("Solicitudes de Acceso Pendientes")
            pending_users = self.supabase.get_pending_users()

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
            emails = self.supabase.get_all_whitelist_emails()

            if emails:
                email_to_remove = st.selectbox("Seleccionar email a remover", emails)
                if st.button("🗑️ Remover Usuario Seleccionado", type="primary"):
                    if self.supabase.remove_email_from_whitelist(email_to_remove):
                        st.success(f"✅ {email_to_remove} removido exitosamente")
                        st.rerun()
                    else:
                        st.error(f"❌ Error al remover {email_to_remove}")
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
