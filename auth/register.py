"""Registration form renderer."""

from __future__ import annotations

import streamlit as st


def render_register_form(crud, security_manager) -> None:
    """Render the registration form for a new user."""

    with st.form("register_form"):
        st.subheader("Create Account")
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register", use_container_width=True)

    if not submitted:
        return

    if not all([full_name, email, username, password, confirm_password]):
        st.error("Please complete every field.")
        return

    if password != confirm_password:
        st.error("Passwords do not match.")
        return

    if len(password) < 8:
        st.error("Use at least 8 characters for the password.")
        return

    existing_user = crud.get_user_by_identifier(email) or crud.get_user_by_identifier(username)
    if existing_user:
        st.error("A user with that email or username already exists.")
        return

    crud.create_user(
        full_name=full_name.strip(),
        email=email.strip().lower(),
        username=username.strip().lower(),
        password_hash=security_manager.hash_password(password),
    )
    st.success("Registration successful. Please sign in.")
