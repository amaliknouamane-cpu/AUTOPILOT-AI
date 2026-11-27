
import streamlit as st
from client_auth import client_login, client_register
from database import read_query

# Page configuration
st.set_page_config(
    page_title="AutoPilot AI - Client Portal",
    page_icon="A",
    layout="wide"
)

# Header
st.title("AutoPilot AI")
st.subheader("Client Portal")

# Authentication
if not st.session_state.get("client_authenticated", False):

    mode = st.radio(
        "Choose an option",
        ["Login", "Create Account"],
        horizontal=True
    )

    if mode == "Login":
        client_login()
    else:
        client_register()

# Client dashboard
else:

    st.success(
        f"Welcome, {st.session_state['client_name']}!"
    )

    st.divider()

    # Client quotations
    st.header("My Quotations")

    quotations = read_query(
        """
        SELECT
            id,
            status,
            total_amount,
            created_at
        FROM quotations
        WHERE customer_id = %s
        ORDER BY created_at DESC;
        """,
        (st.session_state["client_id"],)
    )

    if quotations.empty:
        st.info("You have no quotations yet.")

    else:
        st.dataframe(
            quotations,
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # Logout
    if st.button("Logout"):
        st.session_state["client_authenticated"] = False
        st.session_state.pop("client_id", None)
        st.session_state.pop("client_name", None)
        st.session_state.pop("client_email", None)
        st.session_state.pop("client_phone", None)
        st.rerun()
