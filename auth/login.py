"""Login form renderer."""

from __future__ import annotations

import streamlit as st


def render_login_form(crud, security_manager) -> None:
    """Render the login form and update the session on success."""

    with st.form("login_form"):
        st.subheader("Login")
        identifier = st.text_input("Email or Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if not submitted:
        return

    if not identifier or not password:
        st.error("Please enter both your username/email and password.")
        return

    user = crud.get_user_by_identifier(identifier)
    if user and security_manager.verify_password(password, user["password_hash"]):
        security_manager.login_user(user)
        st.success("Login successful.")
        st.rerun()
        return

    st.error("Invalid credentials. Please try again.")
