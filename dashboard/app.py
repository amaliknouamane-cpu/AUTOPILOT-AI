import streamlit as st
import plotly.express as px
from pathlib import Path
import requests
import pandas as pd 
import subprocess
import sys
import re
import hashlib
import unicodedata
import importlib

from auth import login, logout
from database import read_query, execute_query, get_sales_forecasts
from bi import (
    AT_RISK_DAYS,
    BEST_CUSTOMER_PERCENTILE,
    LOYAL_MIN_APPROVED_QUOTES,
    LOW_STOCK_THRESHOLD,
    NEW_CUSTOMER_DAYS,
    get_approved_sales_lines,
    get_business_kpis,
    get_customer_purchase_summary,
    get_inventory,
    get_monthly_quotation_metrics,
    get_quotation_status_counts,
    segment_customers,
)



# ==================================================
# CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="AutoPilot AI",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded"
)

from backend import ai_service
importlib.reload(ai_service)
extract_quote_information = ai_service.extract_quote_information
extract_quote_items_from_image = ai_service.extract_quote_items_from_image


@st.cache_resource
def get_quote_ocr_engine():
    from rapidocr import RapidOCR
    return RapidOCR()
from speech_input import speech_input
try:
    from backend.agentic_chat.services import agents as agentic_agents
    agentic_agents = importlib.reload(agentic_agents)
    run_agent = agentic_agents.run_agent
    CHATBOT_IMPORT_ERROR = None
except ImportError as error:
    run_agent = None
    CHATBOT_IMPORT_ERROR = error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logo_path = PROJECT_ROOT / "assets" / "autopilot_logo.png"

if logo_path.exists():
    st.sidebar.image(str(logo_path), use_container_width=True)

st.sidebar.markdown(
    "<p style='text-align:center; color:#94c5ff;'>"
    "Intelligent Business Automation</p>",
    unsafe_allow_html=True
)


# ==================================================
# GLOBAL STYLE
# ==================================================

st.markdown("""
<style>
/* Main background */
.stApp {
    background-color: #f4f7fb;
    color: #1e293b;
}
/* Main content */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #14213d;
}
[data-testid="stSidebar"] * {
    color: #ffffff;
}
/* Main text */
.stApp p,
.stApp label,
.stApp span,
.stApp div[data-testid="stMetricLabel"] {
    color: #334155;
}
/* Titles */
h1, h2, h3 {
    color: #14213d !important;
    font-weight: 700;
}
/* Metric cards */
[data-testid="stMetric"] {
    background-color: #ffffff;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
[data-testid="stMetricValue"] {
    color: #14213d !important;
}
/* Dataframes */
[data-testid="stDataFrame"] {
    background-color: #ffffff;
    border-radius: 10px;
}
/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    min-height: 42px;
}
/* Dividers */
hr {
    border-color: #dbe3ef;
}
/* SIDEBAR DESIGN */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #101c35 0%, #1b3155 100%);
    min-width: 280px;
}
/* Sidebar text visibility */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #e2e8f0 !important;
}
/* Application brand */
[data-testid="stSidebar"] h2 {
    color: #ffffff !important;
    font-size: 28px !important;
    font-weight: 800 !important;
    letter-spacing: 1px;
}
/* Navigation spacing */
[data-testid="stSidebar"] [role="radiogroup"] {
    gap: 12px;
}
/* Navigation options */
[data-testid="stSidebar"] [role="radiogroup"] label {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
    padding: 12px 14px;
    min-height: 48px;
    transition: 0.2s ease;
}
/* Hover effect */
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: rgba(59,130,246,0.25);
    border-color: #60a5fa;
}
/* Sidebar buttons */
[data-testid="stSidebar"] .stButton button {
    background: #2563eb;
    color: white !important;
    border: none;
    border-radius: 10px;
    min-height: 45px;
    font-weight: 700;
}
/* Success, warning, error and info messages */
.stAlert,
.stAlert p,
.stAlert div,
.stAlert span {
    color: #ffffff !important;
}
/* Success alert */
.stAlert[data-testid="stAlert"] {
    background-color: #166534 !important;
    border: 1px solid #22c55e !important;
}
/* Download buttons */
.stDownloadButton button {
    background-color: #0877e8 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.stDownloadButton button:hover {
    background-color: #065bb5 !important;
    color: #ffffff !important;
}
/* Text inputs, password fields and number inputs */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stDateInput input {
    background-color: #ffffff !important;
    color: #1e293b !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
}
/* Dropdowns */
.stSelectbox div[data-baseweb="select"] {
    background-color: #ffffff !important;
    color: #1e293b !important;
}
/* All buttons */
.stButton button,
.stFormSubmitButton button {
    background-color: #0877e8 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
/* Button hover */
.stButton button:hover,
.stFormSubmitButton button:hover {
    background-color: #065bb5 !important;
    color: #ffffff !important;
}
/* Data tables */
.stDataFrame {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
}
</style>

""", unsafe_allow_html=True)

def page_header(title, subtitle):
    st.markdown(f"""
    <div style="
        background: linear-gradient(120deg, #14213d, #0877e8);
        padding: 28px 32px;
        border-radius: 16px;
        margin-bottom: 25px;
        box-shadow: 0 5px 18px rgba(20, 33, 61, 0.15);
    ">
        <h1 style="
            color: white !important;
            font-size: 32px;
            margin: 0;
        ">{title}</h1>
        <p style="
            color: #dbeafe !important;
            font-size: 15px;
            margin: 8px 0 0 0;
        ">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)

def clear_client_quote_extraction():
    st.session_state.pop("quote_extracted_items", None)
    st.session_state.pop("quote_unmatched_items", None)
    st.session_state.pop("client_quote_last_response", None)
    st.session_state.pop("quote_image_items", None)
    st.session_state.pop("quote_image_name", None)
    st.session_state.pop("quote_image_digest", None)
    st.session_state["quote_image_upload_version"] = (
        st.session_state.get("quote_image_upload_version", 0) + 1
    )
    st.session_state["quote_image_review_version"] = (
        st.session_state.get("quote_image_review_version", 0) + 1
    )
    st.session_state["quote_voice_ready_to_send"] = False
    for key in list(st.session_state):
        if key.startswith(("qty_", "manual_qty_")):
            st.session_state[key] = 0


def clear_client_quote_request():
    """Clear request widgets from a pre-render callback to avoid Streamlit state errors."""
    st.session_state["quote_request_text"] = ""
    st.session_state["quote_last_transcript"] = ""
    if st.session_state.get("client_quote_input_mode_v3") == "🎙️ Voice":
        st.session_state["quote_speech_component_version"] = (
            st.session_state.get("quote_speech_component_version", 0) + 1
        )
    clear_client_quote_extraction()


_QUOTE_NUMBER_WORDS = {
    "zero": 0, "one": 1, "a": 1, "an": 1, "un": 1, "une": 1,
    "two": 2, "deux": 2, "three": 3, "trois": 3,
    "four": 4, "quatre": 4, "five": 5, "cinq": 5,
    "six": 6, "seven": 7, "sept": 7,
    "eight": 8, "huit": 8, "nine": 9, "neuf": 9,
    "ten": 10, "dix": 10, "eleven": 11, "onze": 11,
    "twelve": 12, "douze": 12, "thirteen": 13, "treize": 13,
    "fourteen": 14, "quatorze": 14, "fifteen": 15, "quinze": 15,
    "sixteen": 16, "seize": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "vingt": 20, "twenty": 20,
    "trente": 30, "thirty": 30, "quarante": 40, "forty": 40,
    "cinquante": 50, "fifty": 50, "soixante": 60, "sixty": 60,
    "cent": 100, "hundred": 100,
}
_QUOTE_TENS = {
    word: value for word, value in _QUOTE_NUMBER_WORDS.items()
    if value in (10, 20, 30, 40, 50, 60)
}
_QUOTE_UNITS = {
    word: value for word, value in _QUOTE_NUMBER_WORDS.items()
    if 1 <= value <= 9
}
_QUOTE_FILLER_WORDS = set(
    (
        "i id would like want need order buy get can could you please the a an "
        "je veux voudrais souhaiterais souhaite commande commander acheter "
        "besoin de du des d et avec pour merci bonjour svp stp s il vous plait "
        "donne donnez ajoute ajouter me moi units unit pieces piece pcs products "
        "product items item quantity quantities and with of for to some few "
        "i would like to have please get me"
    ).split()
)


def _normalize_quote_text(value):
    value = unicodedata.normalize("NFKD", str(value).casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _parse_quote_number(tokens):
    if not tokens:
        return None
    phrase = " ".join(tokens)
    if phrase.isdigit():
        return int(phrase)
    if phrase in _QUOTE_NUMBER_WORDS:
        return _QUOTE_NUMBER_WORDS[phrase]
    if len(tokens) == 2 and tokens[0] in _QUOTE_TENS and tokens[1] in _QUOTE_UNITS:
        return _QUOTE_TENS[tokens[0]] + _QUOTE_UNITS[tokens[1]]
    if (
        len(tokens) == 3
        and tokens[0] in _QUOTE_TENS
        and tokens[1] == "et"
        and tokens[2] in _QUOTE_UNITS
    ):
        return _QUOTE_TENS[tokens[0]] + _QUOTE_UNITS[tokens[2]]
    return None


def _nearby_quote_quantity(tokens):
    tokens = tokens[-4:]
    ignored = {"de", "des", "du", "of", "x", "times", "unit", "units", "pcs"}
    for start in range(len(tokens) - 1, -1, -1):
        candidate = [token for token in tokens[start:] if token not in ignored]
        if len(candidate) <= 3:
            quantity = _parse_quote_number(candidate)
            if quantity is not None:
                return quantity
    return None


def _following_quote_quantity(tokens):
    tokens = tokens[:4]
    if tokens and tokens[0] in {"x", "times", "qty", "quantity"}:
        tokens = tokens[1:]
    for length in (3, 2, 1):
        candidate = tokens[:length]
        while candidate and candidate[-1] in {"unit", "units", "pcs", "pieces", "piece"}:
            candidate = candidate[:-1]
        quantity = _parse_quote_number(candidate)
        if quantity is not None:
            return quantity
    return None


def _fast_extract_catalog_items(message, products):
    normalized_message = _normalize_quote_text(message)
    product_names = products["product_name"].dropna().astype(str).tolist()
    candidates = sorted(
        ((name, _normalize_quote_text(name)) for name in product_names),
        key=lambda pair: len(pair[1]),
        reverse=True,
    )

    matches = []
    for name, normalized_name in candidates:
        if not normalized_name:
            continue
        name_pattern = r"\s+".join(re.escape(part) for part in normalized_name.split())
        pattern = re.compile(rf"(?<![a-z0-9]){name_pattern}(?![a-z0-9])")
        for match in pattern.finditer(normalized_message):
            if any(match.start() < end and match.end() > start for start, end, *_ in matches):
                continue
            matches.append((match.start(), match.end(), name, match.group(0)))

    if not matches:
        return None

    matches.sort(key=lambda row: row[0])
    masked_message = list(normalized_message)
    quantities_by_name = {}
    previous_end = 0
    for match_index, (start, end, name, _) in enumerate(matches):
        next_start = matches[match_index + 1][0] if match_index + 1 < len(matches) else len(normalized_message)
        prefix_tokens = normalized_message[previous_end:start].split()
        suffix_tokens = normalized_message[end:next_start].split()
        quantity = _nearby_quote_quantity(prefix_tokens)
        if quantity is None:
            quantity = _following_quote_quantity(suffix_tokens)
        quantity = quantity if quantity is not None else 1
        if quantity <= 0:
            return None
        quantities_by_name[name] = quantities_by_name.get(name, 0) + quantity
        masked_message[start:end] = " " * (end - start)
        previous_end = end

    residual_words = "".join(masked_message).split()
    unresolved_words = [
        word for word in residual_words
        if not word.isdigit()
        and word not in _QUOTE_NUMBER_WORDS
        and word not in _QUOTE_FILLER_WORDS
    ]
    if unresolved_words:
        return None

    return [
        {"product_name": name, "quantity": quantity}
        for name, quantity in quantities_by_name.items()
    ]


def extract_client_quote_items(message, products):
    product_names = products["product_name"].astype(str).tolist()
    items = _fast_extract_catalog_items(message, products)
    if items is None:
        extracted = extract_quote_information(message, available_products=product_names)
        product_by_key = {name.casefold(): name for name in product_names}
        quantities_by_product = {}
        unmatched = []

        for item in extracted.get("items", []):
            name = product_by_key.get(item["product_name"].casefold())
            if not name:
                unmatched.append(item["product_name"])
                continue
            quantities_by_product[name] = (
                quantities_by_product.get(name, 0) + int(item["quantity"])
            )

        if unmatched:
            raise ValueError("Products not available or not recognized: " + ", ".join(unmatched))
        if not quantities_by_product:
            raise ValueError("No products were recognized in your request.")
        items = [
            {"product_name": name, "quantity": quantity}
            for name, quantity in quantities_by_product.items()
        ]

    stock_by_product = {
        row["product_name"]: int(row["available_stock"])
        for _, row in products.iterrows()
    }
    insufficient = [
        f"{item['product_name']} (requested: {item['quantity']}, available: "
        f"{stock_by_product[item['product_name']]})"
        for item in items
        if item["quantity"] > stock_by_product[item["product_name"]]
    ]
    if insufficient:
        raise ValueError("Insufficient stock: " + "; ".join(insufficient))
    return items


def validate_image_quote_items(items, products):
    product_by_key = {
        _normalize_quote_text(name): name
        for name in products["product_name"].dropna().astype(str)
    }
    quantities_by_product = {}
    unmatched = []
    for item in items:
        key = _normalize_quote_text(item.get("product_name", ""))
        product_name = product_by_key.get(key)
        if not product_name:
            unmatched.append(str(item.get("product_name", "")))
            continue
        quantity = int(item.get("quantity", 0))
        if quantity <= 0:
            continue
        quantities_by_product[product_name] = (
            quantities_by_product.get(product_name, 0) + quantity
        )

    if unmatched:
        raise ValueError(
            "These products could not be matched to the catalogue: "
            + ", ".join(unmatched)
            + ". Edit the request as text or choose the catalogue product manually."
        )
    if not quantities_by_product:
        raise ValueError("No valid product lines were recognized in the image.")

    stock_by_product = {
        row["product_name"]: int(row["available_stock"])
        for _, row in products.iterrows()
    }
    validated = [
        {"product_name": name, "quantity": quantity}
        for name, quantity in quantities_by_product.items()
    ]
    insufficient = [
        f"{item['product_name']} (requested: {item['quantity']}, available: "
        f"{stock_by_product[item['product_name']]})"
        for item in validated
        if item["quantity"] > stock_by_product[item["product_name"]]
    ]
    if insufficient:
        raise ValueError("Insufficient stock: " + "; ".join(insufficient))
    return validated


def _recent_client_quotes(customer_email):
    return read_query(
        """
        SELECT
            q.quote_id::text AS quote_id,
            q.status,
            qi.product_name,
            qi.quantity
        FROM quotations AS q
        JOIN customers AS c ON c.id = q.customer_id
        JOIN quotation_items AS qi ON qi.quotation_id = q.id
        WHERE LOWER(c.email) = LOWER(%s)
          AND q.created_at >= CURRENT_TIMESTAMP - INTERVAL '10 minutes'
        ORDER BY q.created_at DESC;
        """,
        (customer_email.strip(),),
    )


def _find_submitted_quote(customer_email, items, previous_quote_ids):
    try:
        recent_quotes = _recent_client_quotes(customer_email)
    except Exception:
        return None

    if recent_quotes.empty:
        return None

    requested = {}
    for item in items:
        key = str(item["product_name"]).strip().casefold()
        requested[key] = requested.get(key, 0) + int(item["quantity"])

    for quote_id, quote_lines in recent_quotes.groupby("quote_id", sort=False):
        if str(quote_id) in previous_quote_ids:
            continue

        submitted = {}
        for _, line in quote_lines.iterrows():
            key = str(line["product_name"]).strip().casefold()
            submitted[key] = submitted.get(key, 0) + int(line["quantity"])

        if submitted == requested:
            status = str(quote_lines.iloc[0]["status"])
            return {"status": status, "quote_id": str(quote_id)}
    return None


def submit_client_quote(customer_name, customer_email, customer_phone, items, message):
    if not items:
        raise ValueError("Select at least one product.")

    try:
        previous_quote_ids = set(
            _recent_client_quotes(customer_email)["quote_id"].astype(str)
        )
    except Exception:
        previous_quote_ids = None

    try:
        response = requests.post(
            "http://localhost:5678/webhook/quotation_request",
            json={
                "customer_name": customer_name.strip(),
                "customer_email": customer_email.strip(),
                "customer_phone": customer_phone.strip(),
                "source": "client_portal",
                "items": items,
                "message": message.strip(),
            },
            timeout=(10, 15),
        )
    except requests.ReadTimeout:
        # The original n8n workflow waits for the approval step before responding.
        # A read timeout means the request has already been sent; let the workflow
        # finish without making the customer wait for that approval.
        return {"status": "processing"}
    try:
        response_data = response.json()
    except ValueError:
        response_data = None

    workflow_message = (
        str(response_data.get("message", ""))
        if isinstance(response_data, dict)
        else ""
    )
    if "error in workflow" in workflow_message.casefold():
        if previous_quote_ids is not None:
            submitted_quote = _find_submitted_quote(
                customer_email, items, previous_quote_ids
            )
            if submitted_quote is not None:
                return submitted_quote
        raise RuntimeError(
            "We couldn't submit your quotation right now. Please try again in a moment."
        )
    if response.status_code not in (200, 201):
        raise RuntimeError(response.text)
    return response_data if response_data is not None else {"status": "received"}


def _client_quote_error_message(error):
    message = str(error).strip()
    if "error in workflow" in message.casefold():
        return "We couldn't submit your quotation right now. Please try again in a moment."
    if message.casefold().startswith("we couldn't submit your quotation right now"):
        return message
    return f"Unable to prepare the quotation: {message}"


def render_client_portal():
    st.divider()
    st.header("Product Catalogue")

    products = read_query(
        """
        SELECT product AS product_name, available_stock, unit_price
        FROM stock_dashboard
        WHERE available_stock > 0
        ORDER BY product;
        """
    )

    if products.empty:
        st.info("No products are currently available.")
    else:
        st.dataframe(
            products,
            use_container_width=True,
            hide_index=True,
            column_config={
                "product_name": "Product",
                "unit_price": st.column_config.NumberColumn(
                    "Unit Price", format="%.2f MAD"
                ),
                "available_stock": st.column_config.NumberColumn(
                    "Available Stock", format="%d"
                ),
            },
        )

    st.divider()
    st.header("Request a Quotation")

    if not products.empty:

        st.subheader("How would you like to enter your request?")
        quote_input_modes = ["🎙️ Voice", "✍️ Text", "📦 Manual selection"]
        if st.session_state.get("client_quote_input_mode_v3") not in quote_input_modes:
            st.session_state["client_quote_input_mode_v3"] = "📦 Manual selection"
        mode_columns = st.columns(3)
        for column, mode_name in zip(mode_columns, quote_input_modes):
            with column:
                if st.button(
                    mode_name,
                    key=f"select_client_quote_mode_{mode_name}",
                    type=(
                        "primary"
                        if st.session_state["client_quote_input_mode_v3"] == mode_name
                        else "secondary"
                    ),
                    use_container_width=True,
                ):
                    st.session_state["client_quote_input_mode_v3"] = mode_name
                    clear_client_quote_extraction()
                    st.rerun()
        quote_input_mode = st.session_state["client_quote_input_mode_v3"]
        st.session_state.setdefault("quote_image_upload_version", 0)
        st.session_state.setdefault("quote_image_review_version", 0)
        reviewed_image_items = None

        st.subheader("Customer Information")
        customer_name = st.text_input(
            "Full Name",
            value=st.session_state["client_name"],
            key="client_quote_customer_name",
        )
        customer_email = st.text_input(
            "Email",
            value=st.session_state["client_email"],
            disabled=True,
            key="client_quote_customer_email",
        )
        customer_phone = st.text_input(
            "Phone",
            value=st.session_state.get("client_phone") or "",
            key="client_quote_customer_phone",
        )

        if st.session_state.get("client_quote_last_response"):
            st.success("Quotation request received. Its current status is shown below.")
            quote_reference = st.session_state["client_quote_last_response"].get("quote_id")
            if quote_reference:
                st.caption(f"Quotation reference: {quote_reference}")

        if "quote_speech_component_version" not in st.session_state:
            st.session_state["quote_speech_component_version"] = 0
        if "quote_request_text" not in st.session_state:
            st.session_state["quote_request_text"] = ""

        if quote_input_mode == "🎙️ Voice":
            st.caption(
                "Speak your request in French, for example: “Je voudrais cinq ordinateurs portables et trois écrans.”"
            )
            speech_result = speech_input(
                data={"lang": "fr-FR"},
                default={"transcript": ""},
                on_transcript_change=lambda: None,
                on_started_change=lambda: None,
                on_finished_change=lambda: None,
                key=f"client_quote_speech_{st.session_state['quote_speech_component_version']}",
                width="stretch",
                height=56,
            )
            dictated_text = getattr(speech_result, "transcript", "") or ""
            voice_started = False
            started_event = getattr(speech_result, "started", None)
            if isinstance(started_event, dict):
                start_event_id = started_event.get("event_id")
                if start_event_id and start_event_id != st.session_state.get("last_voice_quote_start_id"):
                    st.session_state["last_voice_quote_start_id"] = start_event_id
                    st.session_state["quote_request_text"] = ""
                    st.session_state["quote_last_transcript"] = ""
                    st.session_state["quote_voice_ready_to_send"] = False
                    st.session_state.pop("client_quote_last_response", None)
                    voice_started = True

            finished_event = getattr(speech_result, "finished", None)
            if isinstance(finished_event, dict):
                event_id = finished_event.get("event_id")
                if event_id and event_id != st.session_state.get("last_voice_quote_event_id"):
                    st.session_state["last_voice_quote_event_id"] = event_id
                    dictated_text = str(finished_event.get("transcript") or dictated_text).strip()
                    st.session_state["quote_request_text"] = dictated_text
                    st.session_state["quote_voice_ready_to_send"] = bool(dictated_text)
                    if not dictated_text:
                        st.warning("No speech was recognized. Please try again.")

            if (
                not voice_started
                and dictated_text
                and dictated_text != st.session_state.get("quote_last_transcript")
            ):
                st.session_state["quote_last_transcript"] = dictated_text
                st.session_state["quote_request_text"] = dictated_text

            st.caption(
                "Dictation requires microphone access. Depending on your browser, audio may be "
                "sent to its speech recognition service. Stop recording, review the transcript, "
                "then click “Submit Quotation.”"
            )

            st.text_area(
                "Transcribed message",
                key="quote_request_text",
                height=90,
                on_change=clear_client_quote_extraction,
            )

            st.button(
                "Clear request",
                key="clear_client_quote_request",
                on_click=clear_client_quote_request,
            )

            if st.button(
                "Submit Quotation",
                type="primary",
                key="send_voice_quote",
                use_container_width=True,
            ):
                if not customer_name.strip() or not customer_email.strip():
                    st.error("Check your customer information before submitting.")
                else:
                    try:
                        voice_message = st.session_state.get("quote_request_text", "").strip()
                        if not voice_message:
                            raise ValueError("Stop recording first to capture your message.")
                        with st.spinner("Preparing and submitting your quotation…"):
                            items = extract_client_quote_items(voice_message, products)
                            result = submit_client_quote(
                                customer_name,
                                customer_email,
                                customer_phone,
                                items,
                                voice_message,
                            )
                        st.session_state["client_quote_last_response"] = result
                        st.session_state["quote_voice_ready_to_send"] = False
                        st.rerun()
                    except requests.RequestException as error:
                        st.error(f"Backend connection error: {error}")
                    except Exception as error:
                        st.error(_client_quote_error_message(error))

        elif quote_input_mode == "✍️ Text":
            st.caption("Describe the products and quantities you need.")
            st.text_area(
                "Your request",
                key="quote_request_text",
                height=90,
                placeholder="I would like five laptops and three monitors.",
                on_change=clear_client_quote_extraction,
            )

            st.caption("Or upload a clear photo or scan of your product list (PNG/JPG).")
            uploaded_order_image = st.file_uploader(
                "Order image",
                type=["png", "jpg", "jpeg"],
                key=f"client_quote_image_{st.session_state['quote_image_upload_version']}",
                label_visibility="collapsed",
            )
            if uploaded_order_image is not None:
                image_bytes = uploaded_order_image.getvalue()
                image_digest = hashlib.sha256(image_bytes).hexdigest()
                if image_digest != st.session_state.get("quote_image_digest"):
                    st.session_state.pop("quote_image_items", None)
                    st.session_state.pop("quote_image_name", None)
                    st.session_state.pop("quote_image_digest", None)

                if st.button(
                    "Extract products from image",
                    key="extract_client_quote_image",
                ):
                    try:
                        with st.spinner("Reading product names and quantities with local OCR…"):
                            extracted_image_items = extract_quote_items_from_image(
                                image_bytes,
                                uploaded_order_image.type,
                                products["product_name"].dropna().astype(str).tolist(),
                                ocr_engine=get_quote_ocr_engine(),
                            )
                            validated_image_items = validate_image_quote_items(
                                extracted_image_items,
                                products,
                            )
                        st.session_state["quote_image_items"] = validated_image_items
                        st.session_state["quote_image_name"] = uploaded_order_image.name
                        st.session_state["quote_image_digest"] = image_digest
                        st.session_state["quote_image_review_version"] += 1
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
                    except Exception as error:
                        st.error(f"Could not extract the order image: {error}")

            if st.session_state.get("quote_image_items"):
                st.info(
                    "Products read from the image. Review the names and quantities; "
                    "you can edit quantities before submitting."
                )
                image_review = pd.DataFrame(st.session_state["quote_image_items"])
                reviewed_image_items = st.data_editor(
                    image_review,
                    key=f"client_quote_image_review_{st.session_state['quote_image_review_version']}",
                    use_container_width=True,
                    hide_index=True,
                    disabled=["product_name"],
                    column_config={
                        "product_name": st.column_config.TextColumn("Product"),
                        "quantity": st.column_config.NumberColumn(
                            "Quantity", min_value=1, step=1, format="%d"
                        ),
                    },
                )

            st.button(
                "Clear request",
                key="clear_client_quote_text",
                on_click=clear_client_quote_request,
            )

        elif quote_input_mode == "📦 Manual selection":
            st.info("Choose products and quantities from the list below.")

        if quote_input_mode != "🎙️ Voice":
            selected_items = []
            additional_message = ""
            with st.form(f"client_quote_form_{quote_input_mode}"):
                if quote_input_mode == "📦 Manual selection":
                    st.subheader("Select Products")
                    for _, product in products.iterrows():
                        col1, col2, col3 = st.columns([3, 2, 2])
                        with col1:
                            st.write(product["product_name"])
                        with col2:
                            st.write(f'{product["unit_price"]} MAD')
                        with col3:
                            quantity = st.number_input(
                                "Quantity",
                                min_value=0,
                                max_value=int(product["available_stock"]),
                                value=0,
                                key=f'manual_qty_{product["product_name"]}',
                            )
                        if quantity > 0:
                            selected_items.append({
                                "product_name": product["product_name"],
                                "quantity": int(quantity),
                            })

                    additional_message = st.text_area("Additional Message (Optional)")
                submitted = st.form_submit_button(
                    "Submit Quotation Request",
                    use_container_width=True,
                )

            if submitted:
                if not customer_name.strip() or not customer_email.strip():
                    st.error("Name and email are required.")
                else:
                    try:
                        request_text = ""
                        if quote_input_mode == "✍️ Text":
                            request_text = st.session_state.get("quote_request_text", "").strip()
                            if st.session_state.get("quote_image_items"):
                                if reviewed_image_items is None or reviewed_image_items.empty:
                                    raise ValueError("Review the products extracted from the image first.")
                                selected_items = validate_image_quote_items(
                                    reviewed_image_items.to_dict("records"),
                                    products,
                                )
                                request_text = (
                                    "Products extracted from uploaded image: "
                                    + str(st.session_state.get("quote_image_name", "order image"))
                                )
                            else:
                                if not request_text:
                                    raise ValueError("Enter your request or upload an order image.")
                                with st.spinner("Preparing your quotation…"):
                                    selected_items = extract_client_quote_items(request_text, products)

                        if not selected_items:
                            raise ValueError("Select at least one product.")

                        message = "\n".join(
                            part for part in (request_text, additional_message.strip()) if part
                        )
                        with st.spinner("Submitting your quotation request…"):
                            result = submit_client_quote(
                                customer_name,
                                customer_email,
                                customer_phone,
                                selected_items,
                                message,
                            )
                        st.session_state["client_quote_last_response"] = result
                        st.rerun()
                    except requests.RequestException as error:
                        st.error(f"Backend connection error: {error}")
                    except Exception as error:
                        st.error(_client_quote_error_message(error))
    else:
        st.info("No products are currently available.")



    st.header("My Quotations")

    quotations = read_query(
        """
        SELECT
            quote_id::text AS quote_id,
            status,
            total AS total_amount,
            currency,
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

        st.subheader("Download Quotation PDF")

        project_root = Path(__file__).resolve().parent.parent

        selected_quote_id = st.selectbox(
            "Select a quotation",
            quotations["quote_id"].tolist(),
            format_func=lambda x: str(x)
        )

        selected_status = quotations.loc[
            quotations["quote_id"] == selected_quote_id,
            "status"
        ].iloc[0]

        pdf_path = (
            project_root
            / "documents"
            / f"quotation_{selected_quote_id}.pdf"
        )

        if selected_status == "approved" and pdf_path.exists():

            with open(pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="Download PDF",
                    data=pdf_file,
                    file_name=f"quotation_{selected_quote_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        elif selected_status != "approved":
            st.info("The PDF will be available after your quotation is approved.")

        else:
            st.warning("PDF file not found.")


def render_ai_chatbot():
    st.markdown("""
    <style>
    /* Keep the fixed chat composer readable even when Streamlit uses a dark theme. */
    [data-testid="stBottom"] {
        background: rgba(244, 247, 251, 0.97) !important;
        border-top: 1px solid #dbe3ef !important;
    }
    [data-testid="stChatInput"], [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] div[data-baseweb="textarea"] {
        background: #ffffff !important;
        border-color: #b8c7da !important;
        border-radius: 14px !important;
    }
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInputTextArea"] {
        color: #172b4d !important;
        -webkit-text-fill-color: #172b4d !important;
        caret-color: #0877e8 !important;
        opacity: 1 !important;
        background: #ffffff !important;
        font-size: 16px !important;
    }
    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stChatInputTextArea"]::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }
    [data-testid="stChatInput"] button {
        background: #0877e8 !important;
        color: #ffffff !important;
        border-radius: 10px !important;
    }
    [data-testid="stChatMessage"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        padding: 12px 16px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 14px rgba(20, 33, 61, 0.05) !important;
    }
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] li {
        color: #24364b !important;
    }
    .chatbot-welcome {
        background: linear-gradient(135deg, #ffffff 0%, #edf5ff 100%);
        border: 1px solid #d8e5f4;
        border-radius: 18px;
        padding: 24px 28px;
        margin: 8px 0 20px;
        box-shadow: 0 8px 24px rgba(20, 33, 61, 0.06);
    }
    .chatbot-welcome h3 { color: #14213d !important; margin: 0 0 8px; }
    .chatbot-welcome p { color: #52657c !important; margin: 0; }
    </style>
    """, unsafe_allow_html=True)
    page_header(
        "AutoPilot AI Assistant",
        "Admin assistant for inventory, forecasts, and company knowledge. Quotations are submitted in Client Mode.",
    )

    if run_agent is None:
        st.warning("The chatbot dependencies are not installed in this environment yet.")
        st.code(
            ".venv\\Scripts\\python.exe -m pip install -r backend\\agentic_chat\\requirements.txt",
            language="powershell",
        )
        st.caption(f"Import detail: {CHATBOT_IMPORT_ERROR}")
        return

    if "autopilot_chat_messages" not in st.session_state:
        st.session_state["autopilot_chat_messages"] = []
    if not st.session_state["autopilot_chat_messages"]:
        st.markdown(
            """<div class="chatbot-welcome">
            <h3>What can I help you with?</h3>
            <p>Check stock, review product prices, explore demand forecasts, or search company policies.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        suggestion_columns = st.columns(3)
        suggestions = [
            "Check stock of PS5 CONTROLLER",
            "Forecast demand for Laptop",
            "Show the price of Keyboard",
        ]
        for column, suggestion in zip(suggestion_columns, suggestions):
            with column:
                if st.button(suggestion, key=f"chat_suggestion_{suggestion}", use_container_width=True):
                    st.session_state["autopilot_chat_suggested_prompt"] = suggestion
                    st.rerun()

    for entry in st.session_state["autopilot_chat_messages"]:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])
            if entry.get("route"):
                st.caption(f"Specialist: {entry['route']}")
            if entry.get("sources"):
                st.caption("Sources: " + " · ".join(entry["sources"]))
            details = entry.get("details") or {}
            if details.get("products"):
                products_view = pd.DataFrame(details["products"]).rename(columns={
                    "product_name": "Product",
                    "unit_price": "Unit price (MAD)",
                    "available_stock": "Available stock",
                })
                st.dataframe(products_view, hide_index=True, use_container_width=True)
            if details.get("estimates"):
                estimates_view = pd.DataFrame(details["estimates"]).rename(columns={
                    "product_name": "Product",
                    "estimated_next_7_day_demand": "Estimated demand (next 7 days)",
                })
                st.dataframe(estimates_view, hide_index=True, use_container_width=True)

    prompt = st.chat_input("Type your question here…")
    if not prompt:
        prompt = st.session_state.pop("autopilot_chat_suggested_prompt", None)
    if prompt:
        st.session_state["autopilot_chat_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            with st.chat_message("assistant"):
                with st.spinner("AutoPilot AI is checking your request…"):
                    previous_messages = [
                        {"role": entry["role"], "content": entry["content"]}
                        for entry in st.session_state["autopilot_chat_messages"][:-1][-6:]
                    ]
                    result = run_agent(prompt, history=previous_messages)
                st.markdown(result["answer"])
                st.caption(f"Specialist: {result['route']}")
                if result.get("sources"):
                    st.caption("Sources: " + " · ".join(result["sources"]))
                details = result.get("details") or {}
                if details.get("products"):
                    products_view = pd.DataFrame(details["products"]).rename(columns={
                        "product_name": "Product",
                        "unit_price": "Unit price (MAD)",
                        "available_stock": "Available stock",
                    })
                    st.dataframe(products_view, hide_index=True, use_container_width=True)
                if details.get("estimates"):
                    estimates_view = pd.DataFrame(details["estimates"]).rename(columns={
                        "product_name": "Product",
                        "estimated_next_7_day_demand": "Estimated demand (next 7 days)",
                    })
                    st.dataframe(estimates_view, hide_index=True, use_container_width=True)
            st.session_state["autopilot_chat_messages"].append({
                "role": "assistant",
                "content": result["answer"],
                "route": result["route"],
                "sources": result.get("sources", []),
                "details": details,
            })
        except Exception as error:
            st.error(f"The chatbot could not process the request: {error}")


# ==================================================
# ACCESS MODE SELECTION
# ==================================================

if "access_mode" not in st.session_state:
    st.session_state["access_mode"] = None

if st.session_state["access_mode"] is None:
    st.title("AutoPilot AI")
    st.subheader("Choose Your Access Mode")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Admin Mode", use_container_width=True):
            st.session_state["access_mode"] = "admin"
            st.rerun()
    with col2:
        if st.button("Client Mode", use_container_width=True):
            st.session_state["access_mode"] = "client"
            st.rerun()
    st.stop()


# ==================================================
# ADMIN AUTHENTICATION
# ==================================================

access_mode = st.session_state.get("access_mode")

if access_mode == "admin":
    if not login():
        st.stop()


# ==================================================
# CLIENT AUTHENTICATION
# ==================================================

elif access_mode == "client":
    from client_auth import client_login, client_register

    if not st.session_state.get("client_authenticated", False):
        st.title("AutoPilot AI")
        st.subheader("Client Access")

        client_choice = st.radio(
            "Client Access",
            ["Login", "Create Account"],
            horizontal=True
        )

        if client_choice == "Login":
            client_login()
        else:
            client_register()
        st.stop()

    # Client is authenticated: render only the client portal.
    st.sidebar.markdown(
        f"**CLIENT ACCOUNT**\n\n{st.session_state.get('client_name', 'Client')}"
    )
    if st.sidebar.button("Logout", key="client_logout", use_container_width=True):
        for key in (
            "client_authenticated", "client_id", "client_name",
            "client_email", "client_phone"
        ):
            st.session_state.pop(key, None)
        st.session_state["access_mode"] = None
        st.rerun()

    if st.sidebar.button("Switch Mode", key="client_switch_mode", use_container_width=True):
        for key in (
            "client_authenticated", "client_id", "client_name",
            "client_email", "client_phone"
        ):
            st.session_state.pop(key, None)
        st.session_state["access_mode"] = "admin"
        st.rerun()

    render_client_portal()
    st.stop()


# ==================================================
# ADMIN SIDEBAR PROFILE AND CONTROLS
# ==================================================

st.sidebar.markdown(f"""
<div style="
    background: linear-gradient(135deg, #1e40af, #0877e8);
    padding: 18px;
    border-radius: 14px;
    margin-bottom: 15px;
">
    <div style="font-size:12px; color:#dbeafe;">ADMINISTRATOR ACCOUNT</div>
    <div style="font-size:21px; font-weight:800; color:white; margin-top:8px;">
        {st.session_state.get('username', 'Admin')}
    </div>
    <div style="font-size:13px; color:#dbeafe; margin-top:5px;">
        Role: {st.session_state.get('role', 'ADMIN').upper()}
    </div>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("Logout", key="admin_logout", use_container_width=True):
    logout()

if st.sidebar.button("Switch Mode", key="admin_switch_mode", use_container_width=True):
    st.session_state.pop("authenticated", None)
    st.session_state.pop("username", None)
    st.session_state.pop("role", None)
    st.session_state["access_mode"] = "client"
    st.rerun()


# ==================================================
# ADMIN NAVIGATION
# ==================================================

pages = [
    "Dashboard",
    "AI Chatbot",
    "Products",
    "Quotations",
    "Customers",
    "Analytics",
    "Notification History"
]
if st.session_state.get("role") == "admin":
    pages.append("User Management")
# NEW QUOTATIONS NOTIFICATION

user_id = st.session_state.get("user_id")

# Recover admin ID if missing from session
if user_id is None:
    username = st.session_state.get("username")

    if not username:
        st.error("Admin session not initialized. Please log in again.")
        st.stop()

    user_info = read_query("""
        SELECT id
        FROM dashboard_users
        WHERE LOWER(username) = LOWER(%s)
          AND is_active = TRUE;
    """, (username,))

    if user_info.empty:
        st.error("Administrator account not found.")
        st.stop()

    user_id = int(user_info.iloc[0]["id"])
    st.session_state["user_id"] = user_id

# Count quotations created since the last visit
new_quotes = read_query("""
    SELECT COUNT(*) AS total
    FROM quotations q
    CROSS JOIN dashboard_user_activity a
    WHERE a.user_id = %s
      AND q.created_at > a.last_seen_quotations_at;
""", (user_id,))

new_quotes_count = int(new_quotes.iloc[0]["total"])

if new_quotes_count > 0:
    st.sidebar.info(f"{new_quotes_count} new quotation(s) waiting to be reviewed.")

page = st.sidebar.radio(
    "NAVIGATION",
    pages,
    key="admin_current_page",
)

if page.startswith("Quotations"):
    page = "Quotations"

st.sidebar.divider()
st.sidebar.caption("AutoPilot AI - Commercial Automation")

# DASHBOARD PAGE
# ==================================================

if page == "Dashboard":

    st.markdown("""
<div style="margin-bottom:25px;">
    <h1 style="font-size:32px; margin-bottom:5px;">
        Dashboard Overview
    </h1>
    <p style="color:#64748b; font-size:15px;">
        Monitor your business performance and activities.
    </p>
</div>
""", unsafe_allow_html=True)
    page_header(
    "Dashboard Overview",
    "Monitor your business performance and activities."
)

    try:
        kpis = read_query("SELECT * FROM business_kpis")
        quotations = read_query(
            "SELECT * FROM quotation_dashboard"
        )
        stock = read_query(
            "SELECT * FROM stock_dashboard"
        )

        if kpis.empty:
            st.warning("No business data available.")

        else:
            data = kpis.iloc[0]

            # KPI CARDS
            
            col1, col2, col3, col4 = st.columns(4)

            stats = read_query("""
                  SELECT
                        COUNT(*) AS total_quotes,
                        COUNT(*) FILTER (WHERE status = 'approved') AS approved_quotes,
                        COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_quotes,
                        COUNT(*) FILTER (WHERE status = 'calculated') AS pending_quotes  FROM quotations;
                 """)
            total_quotes = int(stats.iloc[0]["total_quotes"])
            approved_quotes = int(stats.iloc[0]["approved_quotes"])
            rejected_quotes = int(stats.iloc[0]["rejected_quotes"])
            pending_quotes = int(stats.iloc[0]["pending_quotes"])

              
            with col1:
                st.metric(
                   label="Total Quotations",
                   value=total_quotes,
                   help="Total number of quotations"
                )
              
            

            with col2:
                 st.metric(
                   label="Approved",
                   value=approved_quotes
                )

            with col3:
                st.metric(
                    label="Rejected",
                    value=rejected_quotes

        
                  )

            with col4:
                st.metric(
                    label="Pending",
                     value=pending_quotes
                
                 )

            st.divider()

            # REVENUE
            st.subheader("Revenue")

            st.metric(
                "Approved Revenue",
                f'{float(data["approved_revenue"]):,.2f} MAD'
            )

            # CHARTS
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Quotation Status")

                if not quotations.empty:
                    fig = px.pie(
                        quotations,
                        names="status",
                        values="total_quotes",
                        hole=0.4,
                        title="Distribution of Quotations"
                    )

                    st.plotly_chart(
                        fig,
                        use_container_width=True
                    )
                else:
                    st.info("No quotation data available.")

            with col2:
                st.subheader("Stock by Product")

                if not stock.empty:
                    fig = px.bar(
                        stock,
                        x="product",
                        y="available_stock",
                        text="available_stock",
                        title="Available Products"
                    )

                    st.plotly_chart(
                        fig,
                        use_container_width=True
                    )
                else:
                    st.info("No stock data available.")

            # ==========================================
            # LOW STOCK ALERTS
            # ==========================================

            st.divider()
            st.subheader("Low Stock Alerts")

            if not stock.empty:

                low_stock = stock[
                    stock["available_stock"] <= 5
                ].copy()

                if low_stock.empty:
                    st.success(
                        "All products have sufficient stock."
                    )

                else:
                    st.markdown(f"""
<div style="
    background-color: #fee2e2;
    border: 1px solid #ef4444;
    border-left: 6px solid #dc2626;
    color: #991b1b;
    padding: 16px 20px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    margin: 12px 0;
">
    ⚠️ {len(low_stock)} product(s) have low stock!
</div>
""", unsafe_allow_html=True)
                    
                        
                    

                    st.dataframe(
                        low_stock,
                        use_container_width=True,
                        hide_index=True
                    )

            else:
                st.info("No stock information available.")

            # ==========================================
            # COMPLETE INVENTORY
            # ==========================================

            st.divider()
            st.subheader("Inventory")

            st.dataframe(
                stock,
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.subheader("Predicted Sales by Product")

            forecasts = get_sales_forecasts()

            # Select only products that have at least one real sale.
            sold_products = read_query("""
                SELECT DISTINCT item_id
                FROM sales_history
                WHERE target > 0
                ORDER BY item_id;
            """)

            if not sold_products.empty:
                forecasted_product_ids = set(forecasts["item_id"].dropna())
                sold_product_ids = set(sold_products["item_id"].dropna())
                forecasted_sold_count = len(sold_product_ids & forecasted_product_ids)
                missing_forecasts = sorted(sold_product_ids - forecasted_product_ids)

                st.caption(
                    f"Forecast coverage: {forecasted_sold_count} "
                    f"of {len(sold_product_ids)} products with approved sales."
                )
                if missing_forecasts:
                    st.warning(
                        "Forecasts are missing for: " + ", ".join(missing_forecasts)
                    )

                if st.button(
                    "Refresh Sales Predictions",
                    key="refresh_sales_predictions",
                    help="Run Chronos-2 using the latest approved sales in PostgreSQL.",
                ):
                    try:
                        with st.spinner(
                            "Generating forecasts for all products with approved sales..."
                        ):
                            result = subprocess.run(
                                [
                                    sys.executable,
                                    str(PROJECT_ROOT / "test_chronos2.py"),
                                ],
                                cwd=PROJECT_ROOT,
                                capture_output=True,
                                text=True,
                                timeout=900,
                                check=False,
                            )

                        if result.returncode != 0:
                            error_text = (result.stderr or result.stdout)[-3000:]
                            st.error(
                                "Forecast generation failed. "
                                + (error_text or "See the Streamlit server log.")
                            )
                        else:
                            st.success(
                                "Forecasts refreshed from the latest approved sales."
                            )
                            st.rerun()
                    except subprocess.TimeoutExpired:
                        st.error(
                            "Forecast generation exceeded 15 minutes. "
                            "Check the Streamlit server log."
                        )

            if forecasts.empty:
                st.info("No sales forecasts available.")

            elif sold_products.empty:
                st.info("No products have recorded sales yet.")

            else:
                # Keep forecasts only for products with historical sales.
                forecasts = forecasts[
                    forecasts["item_id"].isin(sold_products["item_id"])
                ].copy()

                if forecasts.empty:
                    st.info("No forecasts available for previously sold products.")

                else:
                    forecasts["forecast_date"] = pd.to_datetime(
                        forecasts["forecast_date"]
                    )

                    # Show future forecast dates only.
                    forecasts = forecasts[
                        forecasts["forecast_date"] >= pd.Timestamp.today().normalize()
                    ].copy()

                    if forecasts.empty:
                        st.info("No future forecasts available for previously sold products.")
                    else:
                        chart_data = forecasts.pivot_table(
                            index="forecast_date",
                            columns="item_id",
                            values="predicted_quantity",
                            aggfunc="mean"
                        ).sort_index()

                        # Keep every product with recorded sales in the chart,
                        # including products whose forecast is currently zero.
                        all_sold_items = sorted(
                            sold_products["item_id"].dropna().astype(str).unique()
                        )
                        chart_data.columns = chart_data.columns.astype(str)
                        chart_data = chart_data.reindex(
                            columns=all_sold_items,
                            fill_value=0
                        ).fillna(0)

                        # Showing every product at once makes small forecasts
                        # indistinguishable. Let users focus on meaningful
                        # series while keeping the full data in Forecast Details.
                        chart_data = chart_data.apply(pd.to_numeric, errors="coerce").fillna(0)
                        product_peaks = chart_data.max(axis=0).sort_values(ascending=False)

                        if "forecast_chart_reset_count" not in st.session_state:
                            st.session_state["forecast_chart_reset_count"] = 0
                        selected_product = st.session_state.get("selected_forecast_product")
                        if selected_product not in product_peaks.index:
                            selected_product = None
                            st.session_state["selected_forecast_product"] = None

                        if selected_product:
                            st.caption(f"Selected product: **{selected_product}**")
                            if st.button(
                                "Show all products",
                                key=f"reset_forecast_chart_{st.session_state['forecast_chart_reset_count']}",
                            ):
                                st.session_state["selected_forecast_product"] = None
                                st.session_state["forecast_chart_reset_count"] += 1
                                st.rerun()

                        product_options = ["All products"] + product_peaks.index.tolist()
                        selected_option = selected_product or "All products"
                        product_choice = st.selectbox(
                            "Product to display",
                            product_options,
                            index=product_options.index(selected_option),
                            key=f"forecast_product_focus_{st.session_state['forecast_chart_reset_count']}",
                        )
                        chosen_product = (
                            None if product_choice == "All products" else product_choice
                        )
                        if chosen_product != selected_product:
                            st.session_state["selected_forecast_product"] = chosen_product
                            st.session_state["forecast_chart_reset_count"] += 1
                            st.rerun()

                        control_cols = st.columns([1, 1])
                        with control_cols[0]:
                            product_limit = st.select_slider(
                                "Products shown",
                                options=[5, 10, 15, 20, 30],
                                value=10,
                                key="forecast_chart_product_limit",
                            )

                        max_peak = float(product_peaks.max()) if not product_peaks.empty else 0.0
                        with control_cols[1]:
                            if max_peak > 0:
                                threshold = st.slider(
                                    "Minimum forecast per product",
                                    min_value=0.0,
                                    max_value=max_peak,
                                    value=0.0,
                                    step=max_peak / 100,
                                    key="forecast_chart_threshold",
                                    help="Hide products whose highest forecast is below this value.",
                                )
                            else:
                                threshold = 0.0
                                st.caption("All forecasts are currently zero.")

                        eligible_products = product_peaks[product_peaks >= threshold]
                        visible_products = (
                            [chosen_product]
                            if chosen_product
                            else eligible_products.head(product_limit).index.tolist()
                        )
                        visible_forecasts = forecasts[
                            forecasts["item_id"].astype(str).isin(visible_products)
                        ].copy()
                        visible_forecasts["item_id"] = visible_forecasts["item_id"].astype(str)
                        visible_forecasts["predicted_quantity"] = pd.to_numeric(
                            visible_forecasts["predicted_quantity"], errors="coerce"
                        )

                        if not visible_products:
                            st.info("No products meet this forecast threshold. Lower the threshold to see more.")
                        else:
                            st.caption(
                                f"Showing {len(visible_products)} of {len(product_peaks)} products. "
                                "Click a point on a line to focus on that product."
                            )
                            fig = px.line(
                                visible_forecasts,
                                x="forecast_date",
                                y="predicted_quantity",
                                color="item_id",
                                custom_data=["item_id"],
                                markers=True,
                                template="plotly_dark",
                                labels={
                                    "forecast_date": "Forecast date",
                                    "predicted_quantity": "Predicted quantity",
                                    "color": "Product",
                                },
                            )
                            fig.update_traces(line={"width": 2.5}, marker={"size": 7})
                            fig.update_layout(
                                height=480,
                                hovermode="closest",
                                clickmode="event+select",
                                legend_title_text="Product",
                                margin={"l": 20, "r": 20, "t": 20, "b": 20},
                                paper_bgcolor="#171615",
                                plot_bgcolor="#171615",
                                font={"color": "#e2e8f0"},
                                yaxis={"rangemode": "tozero", "gridcolor": "#353535"},
                                xaxis={"gridcolor": "#353535"},
                            )
                            if threshold > 0:
                                fig.add_hline(
                                    y=threshold,
                                    line_dash="dash",
                                    line_color="#64748b",
                                    annotation_text=f"Seuil : {threshold:g}",
                                    annotation_position="top left",
                                )
                            chart_event = st.plotly_chart(
                                fig,
                                use_container_width=True,
                                theme=None,
                                key=f"forecast_product_chart_{st.session_state['forecast_chart_reset_count']}",
                                on_select="rerun",
                                selection_mode="points",
                            )
                            selected_points = chart_event.selection.get("points", [])
                            if selected_points:
                                custom_data = selected_points[-1].get("customdata") or []
                                clicked_product = str(custom_data[0]) if custom_data else None
                                if clicked_product and clicked_product != st.session_state.get(
                                    "selected_forecast_product"
                                ):
                                    st.session_state["selected_forecast_product"] = clicked_product
                                    st.session_state["forecast_chart_reset_count"] += 1
                                    st.rerun()

                        st.subheader("Forecast Details")

                        st.dataframe(
                            forecasts[[
                                "item_id",
                                "forecast_date",
                                "predicted_quantity",
                                "model_name"
                            ]],
                            use_container_width=True,
                            hide_index=True
                        )


    except Exception as e:
        st.error(f"Dashboard error: {e}")


    

# ==================================================
# PRODUCTS PAGE
# ==================================================

elif page == "AI Chatbot":
    render_ai_chatbot()

elif page == "Products":

    st.title("Products Management")
    st.caption("Manage your product catalogue and inventory.")

    try:

        # LOAD PRODUCTS
        products = read_query(
            "SELECT * FROM stock_dashboard"
        )

        # PRODUCT STATISTICS
        col1, col2 = st.columns(2)

        col1.metric(
            "Total Products",
            len(products)
        )

        total_stock = (
            int(products["available_stock"].sum())
            if not products.empty else 0
        )

        col2.metric(
            "Total Available Units",
            total_stock
        )

        st.divider()

        # PRODUCT CATALOGUE
        st.subheader("Product Catalogue")

        if products.empty:
            st.info("No products found.")

        else:
            st.dataframe(
                products,
                use_container_width=True,
                hide_index=True
            )

        st.divider()

        # ==================================================
        # UPDATE PRODUCT
        # ==================================================

        st.subheader("Update Existing Product")

        editable_products = read_query(
            """
            SELECT id, name, unit_price, stock
            FROM products
            ORDER BY name
            """
        )

        if editable_products.empty:

            st.info("No products available to update.")

        else:

            selected_name = st.selectbox(
                "Select a product",
                editable_products["name"].tolist(),
                key="selected_product"
            )

            selected_product = editable_products[
                editable_products["name"] == selected_name
            ].iloc[0]

            with st.form("update_product_form"):

                new_price = st.number_input(
                    "New Unit Price (MAD)",
                    min_value=0.01,
                    value=float(selected_product["unit_price"]),
                    step=10.0
                )

                new_stock = st.number_input(
                    "New Stock Quantity",
                    min_value=0,
                    value=int(selected_product["stock"]),
                    step=1
                )

                update_submitted = st.form_submit_button(
                    "Update Product",
                    use_container_width=True
                )

                if update_submitted:

                    try:

                        execute_query(
                            """
                            UPDATE products
                            SET unit_price = %s,
                                stock = %s
                            WHERE id = %s
                            """,
                            (
                                new_price,
                                new_stock,
                                int(selected_product["id"])
                            )
                        )

                        st.success(
                            "Product updated successfully!"
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(f"Update error: {e}")

        st.divider()

        # ==================================================
        # ADD PRODUCT
        # ==================================================

        st.subheader("Add New Product")

        with st.form("add_product_form"):

            product_name = st.text_input(
                "Product Name",
                placeholder="Example: Keyboard"
            )

            price = st.number_input(
                "Unit Price (MAD)",
                min_value=0.01,
                value=100.0,
                step=50.0
            )

            stock_quantity = st.number_input(
                "Initial Stock",
                min_value=0,
                value=0,
                step=1
            )

            submitted = st.form_submit_button(
                "Add Product",
                use_container_width=True
            )

            if submitted:

                if not product_name.strip():

                    st.error("Product name is required.")

                else:

                    try:

                        existing = read_query(
                            """
                            SELECT id
                            FROM products
                            WHERE LOWER(name) = LOWER(%s)
                            """,
                            (product_name.strip(),)
                        )

                        if not existing.empty:

                            st.warning(
                                "This product already exists."
                            )

                        else:

                            execute_query(
                                """
                                INSERT INTO products
                                (name, unit_price, stock)
                                VALUES (%s, %s, %s)
                                """,
                                (
                                    product_name.strip(),
                                    price,
                                    stock_quantity
                                )
                            )

                            st.success(
                                "Product added successfully!"
                            )

                            st.rerun()

                    except Exception as e:

                        st.error(
                            f"Database error: {e}"
                        )

        
        st.divider()

        # ==================================================
        # DELETE PRODUCT
        # ==================================================

        st.subheader("Delete Product")

        delete_products = read_query(
            """
            SELECT id, name
            FROM products
            ORDER BY name
            """
        )

        if delete_products.empty:

            st.info("No products available.")

        else:

            delete_name = st.selectbox(
                "Select a product to delete",
                delete_products["name"].tolist(),
                key="delete_product"
            )

            product_to_delete = delete_products[
                delete_products["name"] == delete_name
            ].iloc[0]

            confirm_delete = st.checkbox(
                f"I confirm that I want to delete {delete_name}",
                key="confirm_delete"
            )

            if st.button(
                "Delete Product",
                type="primary",
                use_container_width=True
            ):

                if not confirm_delete:

                    st.warning("Please confirm the deletion.")

                else:

                    try:

                        used_product = read_query(
                            """
                            SELECT id
                            FROM quotation_items
                            WHERE product_id = %s
                            LIMIT 1
                            """,
                            (int(product_to_delete["id"]),)
                        )

                        if not used_product.empty:

                            st.error(
                                "This product cannot be deleted because "
                                "it is used in existing quotations."
                            )

                        else:

                            execute_query(
                                """
                                DELETE FROM products
                                WHERE id = %s
                                """,
                                (int(product_to_delete["id"]),)
                            )

                            st.success(
                                "Product deleted successfully!"
                            )

                            st.rerun()

                    except Exception as e:

                        st.error(f"Delete error: {e}")

    except Exception as e:

        st.error(f"Products page error: {e}")


# ==================================================
# QUOTATIONS PAGE
# ==================================================



elif page == "Quotations":

    execute_query("""
    UPDATE dashboard_user_activity
    SET last_seen_quotations_at = CURRENT_TIMESTAMP
    WHERE user_id = %s;
""", (st.session_state["user_id"],))


    st.title("Quotations Management")
    st.caption("View and manage all customer quotations.")

    try:
        quotations = read_query(
            """
            SELECT
                q.id AS quotation_internal_id,
                q.quote_id::text AS quote_id,
                c.name AS customer_name,
                c.email,
                c.phone,
                q.status,
                q.total,
                q.currency,
                q.created_at
            FROM quotations q
            JOIN customers c ON q.customer_id = c.id
            ORDER BY q.created_at DESC
            """
        )

        if quotations.empty:
            st.info("No quotations found.")

        else:
            # STATISTICS
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Total Quotations", len(quotations))
            col2.metric("Approved", int((quotations["status"] == "approved").sum()))
            col3.metric("Rejected", int((quotations["status"] == "rejected").sum()))
            col4.metric("Pending", int((quotations["status"] == "calculated").sum()))

            st.divider()

            # FILTER
            st.subheader("Quotation List")

            status_options = ["All", "calculated", "approved", "rejected"]

            selected_status = st.selectbox(
                "Filter by status",
                status_options,
                key="quotation_status_filter",
            )

            if selected_status != "All":
                filtered_quotations = quotations[
                    quotations["status"] == selected_status
                ]
            else:
                filtered_quotations = quotations

            st.dataframe(
                filtered_quotations.drop(
                    columns=["quotation_internal_id"],
                    errors="ignore"
                ),
                use_container_width=True,
                hide_index=True
            )

            # DETAILS
            st.divider()
            st.subheader("Quotation Details")

            if not filtered_quotations.empty:

                quote_records = filtered_quotations.to_dict("records")
                quotes_by_id = {
                    record["quote_id"]: record
                    for record in quote_records
                }

                selected_quote_id = st.selectbox(
                    "Select a quotation",
                    list(quotes_by_id),
                    format_func=lambda quote_id: (
                        f"{quotes_by_id[quote_id]['customer_name']} | "
                        f"{quotes_by_id[quote_id]['status']} | "
                        f"{quotes_by_id[quote_id]['total']} "
                        f"{quotes_by_id[quote_id]['currency']} | "
                        f"{quote_id[:8]}"
                    ),
                    key="selected_quotation_id",
                )
                selected_quote = quotes_by_id[selected_quote_id]

                items = read_query(
                    """
                    SELECT product_name, quantity, unit_price, subtotal
                    FROM quotation_items
                    WHERE quotation_id = %s
                    ORDER BY id
                    """,
                    (int(selected_quote["quotation_internal_id"]),)
                )

                detail_col1, detail_col2, detail_col3 = st.columns(3)

                detail_col1.write("**Customer**")
                detail_col1.write(selected_quote["customer_name"])

                detail_col2.write("**Status**")
                detail_col2.write(selected_quote["status"])

                detail_col3.write("**Total**")
                detail_col3.write(
                    f"{selected_quote['total']} {selected_quote['currency']}"
                )

                st.write("**Customer email:**", selected_quote["email"])
                st.write("**Customer phone:**", selected_quote["phone"])
                st.write("**Quotation reference:**", selected_quote["quote_id"])

                st.write("**Products**")

                if items.empty:
                    st.info("No product details found.")
                else:
                    st.dataframe(
                        items,
                        use_container_width=True,
                        hide_index=True
                    )

                # APPROVE / REJECT ACTIONS
                st.divider()
                st.subheader("Quotation Actions")

                if selected_quote["status"] == "calculated":

                    action_col1, action_col2 = st.columns(2)

                    with action_col1:
                        if st.button(
                            "Approve Quotation",
                            type="primary",
                            use_container_width=True,
                            key=f"approve_quotation_{selected_quote['quote_id']}",
                        ):
                            try:
                                response = requests.post(
                                    f"http://127.0.0.1:8001/quotes/{selected_quote['quote_id']}/approve",
                                    timeout=30
                                )

                                if response.status_code == 200:
                                    st.success("Quotation approved successfully!")
                                    st.rerun()
                                else:
                                    st.error(
                                        f"Approval failed: {response.text}"
                                    )

                            except requests.RequestException as e:
                                st.error(f"Connection error: {e}")
                    


                    
                    with action_col2:
                        if st.button(
                            "Reject Quotation",
                            type="secondary",
                            use_container_width=True
                        ):
                            try:
                                response = requests.post(
                                    "http://localhost:5678/webhook/dashboard-rejection",
                                    json={
                                         "quote_id": selected_quote["quote_id"],
                                         "customer_name": selected_quote["customer_name"],
                                          "customer_email": selected_quote["email"]
                                     },
                                     timeout=30      
                                )

                                if response.status_code == 200:
                                    st.success("Quotation rejected and notification sent!")
                                    st.rerun()
                                else:
                                    st.error(
                                        f"Rejection failed: {response.text}"
                                    )

                            except requests.RequestException as e:
                                st.error(f"Connection error: {e}")

                    
                elif selected_quote["status"] == "approved":
                    st.success("This quotation has already been approved.")

                elif selected_quote["status"] == "rejected":
                    st.warning("This quotation has been rejected.")

                # DOWNLOAD PDF
                st.divider()
                st.subheader("Download Quotation PDF")

                project_root = Path(__file__).resolve().parent.parent

                pdf_path = (
                    project_root
                    / "documents"
                    / f"quotation_{selected_quote['quote_id']}.pdf"
                )

                if pdf_path.exists():
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="Download PDF",
                            data=pdf_file,
                            file_name=f"quotation_{selected_quote['quote_id']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                else:
                    st.warning("PDF file not found.")

    except Exception as e:
        st.error(f"Quotations page error: {e}")




# ==================================================
# CUSTOMERS PAGE
# ==================================================


elif page == "Customers":

    st.title("Customers Management")
    st.caption("Manage your customer database.")

    try:
        customers = read_query(
            """
            SELECT
                c.id,
                c.name AS customer_name,
                c.email,
                c.phone,
                c.created_at,
                COUNT(q.id) AS total_quotations,
                COALESCE(
                    SUM(
                        CASE
                            WHEN q.status = 'approved'
                            THEN q.total
                            ELSE 0
                        END
                    ), 0
                ) AS approved_revenue
            FROM customers c
            LEFT JOIN quotations q
                ON c.id = q.customer_id
            GROUP BY
                c.id,
                c.name,
                c.email,
                c.phone,
                c.created_at
            ORDER BY c.created_at DESC
            """
        )

        # CUSTOMER STATISTICS
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Customers",
            len(customers)
        )

        col2.metric(
            "Customers with Quotations",
            int((customers["total_quotations"] > 0).sum())
        )

        col3.metric(
            "Total Approved Revenue",
            f'{customers["approved_revenue"].sum():,.2f} MAD'
        )

        st.divider()

        # CUSTOMER TABLE
        st.subheader("Customer Directory")

        if customers.empty:
            st.info("No customers found.")

        else:
            st.dataframe(
                customers,
                use_container_width=True,
                hide_index=True
            )

    except Exception as e:
        st.error(f"Customers page error: {e}")



# ==================================================
# ANALYTICS PAGE
# ==================================================


elif page == "Analytics":

    from datetime import date, timedelta

    st.title("Business Intelligence")
    st.caption(
        "Live analysis of quotations, approved sales, revenue, and inventory."
    )

    try:
        kpi_frame = get_business_kpis()
        if kpi_frame.empty:
            st.info("No business data is available yet.")
        else:
            kpi = kpi_frame.iloc[0]
            st.caption(
                f"Low stock threshold: {LOW_STOCK_THRESHOLD} units or fewer. "
                "All figures are read directly from PostgreSQL on page load."
            )

            cols = st.columns(5)
            cols[0].metric("Total Quotations", int(kpi["total_quotations"]))
            cols[1].metric("Approved", int(kpi["approved_quotations"]))
            cols[2].metric("Rejected", int(kpi["rejected_quotations"]))
            cols[3].metric("Pending", int(kpi["pending_quotations"]))
            cols[4].metric(
                "Approved Revenue",
                f'{float(kpi["approved_revenue"]):,.2f} MAD',
                help="Revenue from approved quotations only.",
            )

            cols = st.columns(5)
            cols[0].metric("Approval Rate", f'{float(kpi["approval_rate"]):.2f}%')
            cols[1].metric("Rejection Rate", f'{float(kpi["rejection_rate"]):.2f}%')
            cols[2].metric(
                "Average Quotation Value",
                f'{float(kpi["average_quotation_value"]):,.2f} MAD',
                help="Average value across all quotations, including pending and rejected.",
            )
            cols[3].metric("Total Products", int(kpi["total_products"]))
            cols[4].metric("Low Stock Products", int(kpi["low_stock_products"]))

        st.divider()
        st.subheader("Quotation Analysis")
        status_data = get_quotation_status_counts()
        monthly = get_monthly_quotation_metrics()

        left, right = st.columns(2)
        with left:
            if status_data.empty:
                st.info("No quotations have been created yet.")
            else:
                status_data["status_label"] = status_data["status"].map(
                    {"approved": "Approved", "rejected": "Rejected", "calculated": "Pending"}
                ).fillna(status_data["status"].str.title())
                fig = px.pie(
                    status_data,
                    names="status_label",
                    values="total_quotations",
                    hole=0.48,
                    title="Quotation Distribution by Status",
                    color="status_label",
                    color_discrete_map={
                        "Approved": "#16a34a",
                        "Rejected": "#dc2626",
                        "Pending": "#f59e0b",
                    },
                )
                fig.update_layout(legend_title_text="Status")
                st.plotly_chart(fig, width="stretch")

        with right:
            if monthly.empty:
                st.info("No monthly quotation data is available.")
            else:
                monthly_plot = monthly.melt(
                    id_vars="month",
                    value_vars=[
                        "approved_quotations",
                        "rejected_quotations",
                        "pending_quotations",
                    ],
                    var_name="status",
                    value_name="quotations",
                )
                monthly_plot["status"] = monthly_plot["status"].map(
                    {
                        "approved_quotations": "Approved",
                        "rejected_quotations": "Rejected",
                        "pending_quotations": "Pending",
                    }
                )
                fig = px.line(
                    monthly_plot,
                    x="month",
                    y="quotations",
                    color="status",
                    markers=True,
                    title="Monthly Quotation Trend",
                    labels={"month": "Month", "quotations": "Quotations", "status": "Status"},
                    color_discrete_map={
                        "Approved": "#16a34a",
                        "Rejected": "#dc2626",
                        "Pending": "#f59e0b",
                    },
                )
                st.plotly_chart(fig, width="stretch")

        if not monthly.empty:
            st.subheader("Approved Revenue by Month")
            st.caption(
                "Grouped by quotation creation month; the database does not store a separate approval date."
            )
            fig = px.line(
                monthly,
                x="month",
                y="approved_revenue",
                markers=True,
                title="Monthly Revenue (Approved Quotations Only)",
                labels={
                    "month": "Month",
                    "approved_revenue": "Approved Revenue (MAD)",
                },
            )
            fig.update_traces(line_color="#2563eb")
            st.plotly_chart(fig, width="stretch")

        st.divider()
        st.subheader("Sales Analysis")
        approved_lines = get_approved_sales_lines()
        inventory = get_inventory()

        if approved_lines.empty:
            st.info("There are no approved quotation items to analyze as sales yet.")
            sales_summary = pd.DataFrame(columns=["product", "quantity_sold", "sales_revenue"])
        else:
            approved_lines["quantity"] = pd.to_numeric(
                approved_lines["quantity"], errors="coerce"
            ).fillna(0)
            approved_lines["revenue"] = pd.to_numeric(
                approved_lines["revenue"], errors="coerce"
            ).fillna(0)
            approved_lines["sale_date"] = pd.to_datetime(
                approved_lines["sale_date"], errors="coerce"
            ).dt.date
            sales_summary = (
                approved_lines.groupby("product", as_index=False)
                .agg(quantity_sold=("quantity", "sum"), sales_revenue=("revenue", "sum"))
            )

        if not inventory.empty:
            inventory["product_key"] = inventory["product"].astype(str).str.casefold()
            sales_summary["product_key"] = sales_summary["product"].astype(str).str.casefold()
            performance = inventory.merge(
                sales_summary.drop(columns="product"),
                on="product_key",
                how="left",
            )
            performance["quantity_sold"] = performance["quantity_sold"].fillna(0)
            performance["sales_revenue"] = performance["sales_revenue"].fillna(0)
            performance = performance.drop(columns="product_key")
        else:
            performance = sales_summary.copy()
            performance["available_stock"] = 0
            performance["stock_value"] = 0

        if not sales_summary.empty:
            chart_limit = st.select_slider(
                "Products shown in sales charts",
                options=[5, 10, 20, 50],
                value=10,
            )
            best_sellers = sales_summary.sort_values(
                ["quantity_sold", "sales_revenue"], ascending=False
            ).head(chart_limit)
            top_revenue = sales_summary.sort_values(
                ["sales_revenue", "quantity_sold"], ascending=False
            ).head(chart_limit)

            left, right = st.columns(2)
            with left:
                fig = px.bar(
                    best_sellers.sort_values("quantity_sold"),
                    x="quantity_sold",
                    y="product",
                    orientation="h",
                    title="Best-Selling Products by Quantity",
                    labels={"quantity_sold": "Units Sold", "product": "Product"},
                    text="quantity_sold",
                )
                fig.update_traces(marker_color="#2563eb")
                st.plotly_chart(fig, width="stretch")
            with right:
                fig = px.bar(
                    top_revenue.sort_values("sales_revenue"),
                    x="sales_revenue",
                    y="product",
                    orientation="h",
                    title="Revenue by Product",
                    labels={"sales_revenue": "Revenue (MAD)", "product": "Product"},
                    text="sales_revenue",
                )
                fig.update_traces(marker_color="#0f766e")
                st.plotly_chart(fig, width="stretch")

            low_sales = performance.sort_values(
                ["quantity_sold", "sales_revenue", "product"], ascending=[True, True, True]
            ).head(10)
            st.markdown("**Lowest-selling products** (includes products with zero approved sales).")
            st.dataframe(
                low_sales[["product", "quantity_sold", "sales_revenue", "available_stock"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "quantity_sold": st.column_config.NumberColumn("Units Sold", format="%d"),
                    "sales_revenue": st.column_config.NumberColumn("Revenue (MAD)", format="%.2f"),
                    "available_stock": st.column_config.NumberColumn("Available Stock", format="%d"),
                },
            )

            st.markdown("**Approved sales by product**")
            st.dataframe(
                sales_summary.sort_values("sales_revenue", ascending=False),
                width="stretch",
                hide_index=True,
                column_config={
                    "quantity_sold": st.column_config.NumberColumn("Units Sold", format="%d"),
                    "sales_revenue": st.column_config.NumberColumn("Revenue (MAD)", format="%.2f"),
                },
            )
        else:
            st.info("No approved sales are available for product analysis.")

        st.divider()
        st.subheader("Customer Segmentation")
        customer_segments = segment_customers(get_customer_purchase_summary())

        st.caption(
            f"New: exactly one approved purchase, first made in the last {NEW_CUSTOMER_DAYS} days. "
            "Customers without an approved purchase are Prospects. "
            f"At Risk: no approved purchase in over {AT_RISK_DAYS} days. "
            f"Loyal: at least {LOYAL_MIN_APPROVED_QUOTES} approved quotations and active within "
            f"{AT_RISK_DAYS} days. Best Customers: active repeat buyers in the top "
            f"{int((1 - BEST_CUSTOMER_PERCENTILE) * 100)}% by approved revenue."
        )

        if customer_segments.empty:
            st.info("No customer records are available for segmentation.")
        else:
            segment_order = [
                "Best Customers",
                "Loyal",
                "New",
                "At Risk",
                "Occasional",
                "Prospect",
            ]
            segment_counts = (
                customer_segments.groupby("segment", as_index=False)
                .agg(customer_count=("customer_id", "count"))
            )
            segment_revenue = (
                customer_segments.groupby("segment", as_index=False)
                .agg(approved_revenue=("approved_revenue", "sum"))
            )

            count_by_segment = segment_counts.set_index("segment")["customer_count"]
            cols = st.columns(4)
            cols[0].metric("Loyal Customers", int(count_by_segment.get("Loyal", 0)))
            cols[1].metric("New Customers", int(count_by_segment.get("New", 0)))
            cols[2].metric("At-Risk Customers", int(count_by_segment.get("At Risk", 0)))
            cols[3].metric(
                "Best Customers",
                int(count_by_segment.get("Best Customers", 0)),
            )

            left, right = st.columns(2)
            with left:
                fig = px.pie(
                    segment_counts,
                    names="segment",
                    values="customer_count",
                    category_orders={"segment": segment_order},
                    hole=0.45,
                    title="Customers by Segment",
                    color="segment",
                    color_discrete_map={
                        "Best Customers": "#7c3aed",
                        "Loyal": "#16a34a",
                        "New": "#2563eb",
                        "At Risk": "#dc2626",
                        "Occasional": "#f59e0b",
                        "Prospect": "#64748b",
                    },
                )
                st.plotly_chart(fig, width="stretch")

            with right:
                fig = px.bar(
                    segment_revenue.sort_values("approved_revenue"),
                    x="approved_revenue",
                    y="segment",
                    orientation="h",
                    category_orders={"segment": segment_order},
                    title="Approved Revenue by Customer Segment",
                    labels={
                        "approved_revenue": "Approved Revenue (MAD)",
                        "segment": "Segment",
                    },
                    text="approved_revenue",
                )
                st.plotly_chart(fig, width="stretch")

            selected_segment = st.selectbox(
                "Filter customers by segment",
                ["All"] + segment_order,
                key="bi_customer_segment_filter",
            )
            segment_table = customer_segments
            if selected_segment != "All":
                segment_table = segment_table[
                    segment_table["segment"] == selected_segment
                ]

            st.dataframe(
                segment_table[[
                    "customer",
                    "segment",
                    "customer_since",
                    "approved_order_count",
                    "approved_revenue",
                    "first_purchase_at",
                    "last_purchase_at",
                    "days_since_last_purchase",
                ]].sort_values(
                    ["segment", "approved_revenue"],
                    ascending=[True, False],
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "approved_order_count": st.column_config.NumberColumn(
                        "Approved Quotations", format="%d"
                    ),
                    "customer_since": st.column_config.DateColumn(
                        "Customer Since"
                    ),
                    "approved_revenue": st.column_config.NumberColumn(
                        "Approved Revenue (MAD)", format="%.2f"
                    ),
                    "first_purchase_at": st.column_config.DateColumn(
                        "First Approved Purchase"
                    ),
                    "last_purchase_at": st.column_config.DateColumn(
                        "Last Approved Purchase"
                    ),
                    "days_since_last_purchase": st.column_config.NumberColumn(
                        "Days Since Last Purchase", format="%d"
                    ),
                },
            )

        st.subheader("Period Comparison")
        st.caption(
            "Period comparisons use approved quotation items and their quotation creation dates."
        )
        today = date.today()
        start_default = today - timedelta(days=29)
        period = st.date_input(
            "Select the current period",
            value=(start_default, today),
            max_value=today,
            key="bi_sales_period",
        )
        if isinstance(period, (tuple, list)) and len(period) == 2:
            current_start, current_end = period
        else:
            current_start = current_end = period

        if current_start and current_end and current_start <= current_end:
            period_days = (current_end - current_start).days + 1
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end - timedelta(days=period_days - 1)

            if approved_lines.empty:
                current_sales = previous_sales = approved_lines
            else:
                current_sales = approved_lines[
                    approved_lines["sale_date"].between(current_start, current_end)
                ]
                previous_sales = approved_lines[
                    approved_lines["sale_date"].between(previous_start, previous_end)
                ]

            current_revenue = float(current_sales["revenue"].sum()) if not current_sales.empty else 0.0
            previous_revenue = float(previous_sales["revenue"].sum()) if not previous_sales.empty else 0.0
            current_quantity = int(current_sales["quantity"].sum()) if not current_sales.empty else 0
            previous_quantity = int(previous_sales["quantity"].sum()) if not previous_sales.empty else 0
            revenue_delta = current_revenue - previous_revenue
            quantity_delta = current_quantity - previous_quantity

            cols = st.columns(4)
            cols[0].metric(
                "Current-Period Revenue",
                f"{current_revenue:,.2f} MAD",
                delta=f"{revenue_delta:+,.2f} MAD vs prior period",
            )
            cols[1].metric(
                "Current-Period Units Sold",
                current_quantity,
                delta=f"{quantity_delta:+d} units vs prior period",
            )
            cols[2].metric("Current Period", f"{current_start} to {current_end}")
            cols[3].metric("Comparison Period", f"{previous_start} to {previous_end}")
        else:
            st.info("Choose a valid start and end date to compare periods.")

        st.divider()
        st.subheader("Inventory and Restocking")
        if inventory.empty:
            st.info("No products are registered in inventory.")
        else:
            inventory_analysis = inventory.copy()
            inventory_analysis["product_key"] = inventory_analysis["product"].astype(str).str.casefold()
            if not approved_lines.empty:
                recent_start = today - timedelta(days=29)
                recent_lines = approved_lines[
                    approved_lines["sale_date"] >= recent_start
                ]
                recent_sales = recent_lines.groupby(
                    recent_lines["product"].str.casefold()
                )["quantity"].sum()
                recent_sales.index.name = "product_key"
                inventory_analysis = inventory_analysis.merge(
                    recent_sales.rename("units_sold_last_30_days"),
                    left_on="product_key",
                    right_index=True,
                    how="left",
                )
            else:
                inventory_analysis["units_sold_last_30_days"] = 0

            inventory_analysis["units_sold_last_30_days"] = inventory_analysis[
                "units_sold_last_30_days"
            ].fillna(0)
            inventory_analysis["average_daily_sales"] = (
                inventory_analysis["units_sold_last_30_days"] / 30
            )
            inventory_analysis["estimated_days_of_stock"] = (
                inventory_analysis["available_stock"]
                / inventory_analysis["average_daily_sales"].replace(0, pd.NA)
            )
            inventory_analysis["low_stock"] = (
                inventory_analysis["available_stock"] <= LOW_STOCK_THRESHOLD
            )
            inventory_analysis["restock_recommended"] = (
                inventory_analysis["low_stock"]
                | (inventory_analysis["estimated_days_of_stock"] <= 14)
            )

            restock = inventory_analysis[inventory_analysis["restock_recommended"]].copy()
            if restock.empty:
                st.success("No products currently meet the restocking alert rules.")
            else:
                st.warning(
                    f"{len(restock)} product(s) are low in stock or have 14 days or less of estimated stock cover."
                )
                st.dataframe(
                    restock[[
                        "product",
                        "available_stock",
                        "units_sold_last_30_days",
                        "estimated_days_of_stock",
                        "stock_value",
                    ]],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "available_stock": st.column_config.NumberColumn("Available Stock", format="%d"),
                        "units_sold_last_30_days": st.column_config.NumberColumn("Units Sold (30d)", format="%d"),
                        "estimated_days_of_stock": st.column_config.NumberColumn("Estimated Days of Stock", format="%.1f"),
                        "stock_value": st.column_config.NumberColumn("Stock Value (MAD)", format="%.2f"),
                    },
                )

            left, right = st.columns(2)
            with left:
                stock_chart = inventory_analysis.sort_values("available_stock", ascending=False)
                fig = px.bar(
                    stock_chart,
                    x="product",
                    y="available_stock",
                    title="Available Stock by Product",
                    labels={"product": "Product", "available_stock": "Units in Stock"},
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, width="stretch")
            with right:
                fig = px.bar(
                    inventory_analysis.sort_values("stock_value", ascending=False),
                    x="product",
                    y="stock_value",
                    title="Inventory Value by Product",
                    labels={"product": "Product", "stock_value": "Stock Value (MAD)"},
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, width="stretch")

            st.markdown("**Available inventory and approved sales**")
            st.dataframe(
                performance[[
                    "product",
                    "quantity_sold",
                    "sales_revenue",
                    "available_stock",
                    "stock_value",
                ]].sort_values("product"),
                width="stretch",
                hide_index=True,
                column_config={
                    "quantity_sold": st.column_config.NumberColumn("Approved Units Sold", format="%d"),
                    "sales_revenue": st.column_config.NumberColumn("Approved Revenue (MAD)", format="%.2f"),
                    "available_stock": st.column_config.NumberColumn("Available Stock", format="%d"),
                    "stock_value": st.column_config.NumberColumn("Stock Value (MAD)", format="%.2f"),
                },
            )

    except Exception as e:
        st.error(f"Business Intelligence error: {e}")


# ==================================================
# USER MANAGEMENT PAGE
# ==================================================

elif page == "User Management":

    st.title("Administrator Management")
    st.caption("Create and manage administrator accounts.")

    if st.session_state.get("role") != "admin":
        st.error("Access denied.")
        st.stop()

    # CREATE ADMINISTRATOR
    st.subheader("Create New Administrator")

    with st.form("create_admin_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        submitted = st.form_submit_button("Create Administrator")

        if submitted:
            if not new_username.strip() or not new_password:
                st.error("All fields are required.")

            elif new_password != confirm_password:
                st.error("Passwords do not match.")

            else:
                try:
                    password_hash = bcrypt.hashpw(
                        new_password.encode("utf-8"),
                        bcrypt.gensalt()
                    ).decode("utf-8")

                    execute_query(
                        """
                        INSERT INTO dashboard_users
                            (username, password_hash, role)
                        VALUES (%s, %s, 'admin');
                        """,
                        (new_username.strip(), password_hash)
                    )

                    st.success("Administrator created successfully.")
                    st.rerun()

                except Exception as e:
                    st.error(f"Could not create administrator: {e}")

    st.divider()

    # DISPLAY ADMINISTRATORS
    st.subheader("Registered Administrators")

    users = read_query(
        """
        SELECT id, username, role, is_active, created_at
        FROM dashboard_users
        ORDER BY id;
        """
    )

    st.dataframe(
        users,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # DEACTIVATE ADMINISTRATOR
    st.subheader("Deactivate Administrator")

    other_users = users[
        (users["is_active"] == True) &
        (users["username"] != st.session_state["username"])
    ]

    if other_users.empty:
        st.info("No other active administrators to deactivate.")

    else:
        selected_user = st.selectbox(
            "Select an administrator",
            options=other_users["id"].tolist(),
            format_func=lambda user_id: other_users.loc[
                other_users["id"] == user_id,
                "username"
            ].iloc[0]
        )

        if st.button("Deactivate Account"):
            execute_query(
                """
                UPDATE dashboard_users
                SET is_active = FALSE
                WHERE id = %s
                  AND username <> %s;
                """,
                (selected_user, st.session_state["username"])
            )

            st.success("Administrator deactivated.")
            st.rerun()


elif page == "Notification History":

    st.title("Notification History")
    st.caption("History of quotation notifications.")

    notifications = read_query(
        """
        SELECT
            id,
            quote_id,
            recipient,
            notification_type,
            subject,
            message,
            status,
            created_at
        FROM notifications
        ORDER BY created_at DESC;
        """
    )

    if notifications.empty:
        st.info("No notifications found.")

    else:
        st.metric("Total Notifications", len(notifications))

        st.dataframe(
            notifications,
            use_container_width=True,
            hide_index=True
        )
