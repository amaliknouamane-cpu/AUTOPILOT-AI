
import streamlit as st
import bcrypt
from database import read_query


def client_login():
    st.title("AutoPilot AI")
    st.subheader("Client Login")

    with st.form("client_login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        result = read_query(
            """
            SELECT id, name, email, phone, password_hash
            FROM customers
            WHERE LOWER(email) = LOWER(%s)
              AND is_active = TRUE;
            """,
            (email.strip(),)
        )

        if not result.empty:
            stored_hash = result.iloc[0]["password_hash"]

            if stored_hash and bcrypt.checkpw(
                password.encode("utf-8"),
                stored_hash.encode("utf-8")
            ):
                st.session_state["client_authenticated"] = True
                st.session_state["client_id"] = int(result.iloc[0]["id"])
                st.session_state["client_name"] = result.iloc[0]["name"]
                st.session_state["client_email"] = result.iloc[0]["email"]
                st.session_state["client_phone"] = result.iloc[0]["phone"] or ""
                st.rerun()

        st.error("Invalid email or password.")

    return st.session_state.get("client_authenticated", False)
def client_register():
    st.subheader("Create a Client Account")

    with st.form("client_register_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        submitted = st.form_submit_button("Create Account")

    if submitted:
        if not all([name.strip(), email.strip(), password, confirm_password]):
            st.error("Please fill in all required fields.")

        elif password != confirm_password:
            st.error("Passwords do not match.")

        elif len(password) < 8:
            st.error("Password must contain at least 8 characters.")

        else:
            existing = read_query(
                "SELECT id FROM customers WHERE LOWER(email) = LOWER(%s)",
                (email.strip(),)
            )

            if not existing.empty:
                st.error("This email is already registered.")

            else:
                from database import execute_query

                password_hash = bcrypt.hashpw(
                    password.encode("utf-8"),
                    bcrypt.gensalt()
                ).decode("utf-8")

                execute_query(
                    """
                    INSERT INTO customers
                        (name, email, phone, password_hash, is_active)
                    VALUES (%s, %s, %s, %s, TRUE);
                    """,
                    (
                        name.strip(),
                        email.strip(),
                        phone.strip(),
                        password_hash
                    )
                )

                st.success("Account created successfully. You can now log in.")
