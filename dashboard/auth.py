
import streamlit as st
import bcrypt
from database import read_query


def login():
    if not st.session_state.get("authenticated", False):
        st.title("AutoPilot AI")
        st.subheader("Administrator Login")

    # Vérifier si l'utilisateur est déjà connecté
    if st.session_state.get("authenticated", False):

        result = read_query(
            """
            SELECT id, username, role
            FROM dashboard_users
            WHERE LOWER(username) = LOWER(%s)
              AND is_active = TRUE;
            """,
            (st.session_state["username"],)
        )

        if not result.empty:
            st.session_state["user_id"] = int(result.iloc[0]["id"])
            st.session_state["role"] = result.iloc[0]["role"]
            return True

        # Compte désactivé
        st.session_state["authenticated"] = False
        st.session_state.pop("username", None)
        st.session_state.pop("user_id", None)
        st.session_state.pop("role", None)
        st.rerun()

    # Formulaire de connexion
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        result = read_query(
            """
            SELECT id, username, password_hash, role
            FROM dashboard_users
            WHERE LOWER(username) = LOWER(%s)
              AND is_active = TRUE;
            """,
            (username.strip(),)
        )

        if not result.empty:
            user = result.iloc[0]

            if bcrypt.checkpw(
                password.encode("utf-8"),
                user["password_hash"].encode("utf-8")
            ):
                st.session_state["authenticated"] = True
                st.session_state["user_id"] = int(user["id"])
                st.session_state["username"] = user["username"]
                st.session_state["role"] = user["role"]

                st.rerun()

        st.error("Invalid username or password.")

    return False


def logout():
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.session_state.pop("user_id", None)
    st.session_state.pop("role", None)
    st.rerun()
