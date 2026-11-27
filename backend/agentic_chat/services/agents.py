"""Supervisor and specialist nodes composed with LangGraph."""
from typing import Literal, TypedDict
import re
import unicodedata

from langgraph.graph import END, START, StateGraph

from .business_tools import (
    forecast_product_demand,
    list_catalogue,
)
from .knowledge import answer_from_knowledge
from .ollama import chat
from .observability import RunRecorder

ROUTES = {"inventory", "forecast", "client_portal", "knowledge", "general"}


class AgentState(TypedDict, total=False):
    query: str
    history: list[dict]
    route: str
    answer: str
    sources: list[str]
    details: dict
    matched_products: list[str]
    context_query: str


PRODUCT_ALIASES = {
    "SAMSUNG TV": (
        "tv samsung", "samsung television", "samsung smart tv", "smart tv samsung",
        "smart television", "television", "tv", "samsung television set",
    ),
    "PLAYSTATION 5": (
        "ps5", "ps 5", "sony playstation 5", "play station 5", "playstation console",
        "sony console",
    ),
    "PS5 CONTROLLER": (
        "ps5 controller", "ps 5 controller", "dualsense", "dual sense", "ps5 gamepad",
        "playstation 5 controller", "playstation controller", "ps 5 controller",
        "playstation 5 gamepad", "game controller", "controller", "gamepad", "manette",
        "controller ps5", "manette ps5", "manette playstation",
    ),
    "SAMSUNG 26 ULTRA": (
        "samsung galaxy 26 ultra", "galaxy 26 ultra", "samsung s26 ultra", "s26 ultra",
    ),
    "IPHONE 18 PRO": (
        "iphone", "iphone pro", "iphone 18", "apple iphone", "apple phone", "apple smartphone",
    ),
    "KEYBORD": ("keyboard", "key board"),
    "LAPTOP": ("notebook", "portable computer", "laptop computer", "ordinateur portable", "pc portable"),
    "MONITOR": ("screen", "display", "computer screen", "ecran", "écran"),
    "GRAPHICS CARD": ("gpu", "video card", "graphic card", "carte graphique"),
    "RAM 16GB": ("ram", "16gb ram", "memory 16gb", "16 gb memory", "memoire vive"),
    "SSD 1TB": ("ssd", "1tb ssd", "solid state drive", "1 tb ssd"),
    "WIRELESS MOUSE": ("mouse", "wireless mouse", "computer mouse", "souris sans fil"),
    "COFFEE MACHINE": ("coffee maker", "espresso machine", "machine a cafe", "cafetière"),
    "EXTERNAL HARD DRIVE": ("external drive", "hard drive", "portable hard drive", "disque dur externe"),
    "USB FLASH DRIVE": ("usb drive", "flash drive", "usb key", "cle usb", "clé usb"),
    "CPU AMD RYZEN 7": ("amd ryzen 7", "ryzen 7", "ryzen seven", "processeur amd"),
    "FC 27": ("fc27", "fifa 27", "ea sports fc 27", "ea fc 27"),
    "GPS TRACKER": ("gps", "gps device", "traceur gps"),
    "HEADPHONES": ("headphone", "headset", "earphones", "casque audio", "écouteurs"),
    "MICROPHONE": ("mic", "micro", "microphone usb"),
    "NETWORK SWITCH": ("ethernet switch", "networking switch", "commutateur réseau"),
    "POWER BANK": ("powerbank", "portable charger", "battery pack", "batterie externe"),
    "PRINTER": ("printing machine", "imprimante"),
    "PROJECTOR": ("beamer", "projecteur"),
    "RDD 2": ("rdd2",),
    "RESIDENT EVIL 10": ("resident evil 10", "resident evil x", "re10"),
    "ROUTER": ("wifi router", "wireless router", "routeur"),
    "WEBCAM": ("web camera", "camera web", "web cam"),
    "TESLA MODEL S PLAID": ("model s plaid", "tesla plaid",),
}


def _normalize_product_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _wants_full_catalogue(query: str) -> bool:
    normalized = _normalize_product_text(query)
    padded = f" {normalized} "
    phrases = (
        "all products", "show all products", "list all products", "full catalogue",
        "all catalogue", "what products", "which products", "what products do you sell",
        "what do you sell", "what do you offer", "show me products", "list products",
        "product list", "product catalogue", "product catalog", "show catalogue", "show catalog",
        "tous les produits", "liste des produits", "quels produits vendez vous",
        "catalogue complet", "catalogue entier", "montre moi les produits",
    )
    return any(f" {_normalize_product_text(phrase)} " in padded for phrase in phrases)


def _catalogue_mentions(query: str, catalogue: list[dict]) -> list[dict]:
    normalized_query = _normalize_product_text(query)
    query_tokens = set(normalized_query.split())
    padded_query = f" {normalized_query} "
    matches = []
    for product in catalogue:
        name = product["product_name"]
        if name.upper() == "PLAYSTATION 5" and "controller" in query_tokens:
            continue
        normalized_name = _normalize_product_text(name)
        variants = [normalized_name, *(
            _normalize_product_text(alias)
            for alias in PRODUCT_ALIASES.get(name.upper(), ())
        )]
        if any(f" {variant} " in padded_query for variant in variants):
            matches.append(product)
    return matches


def _is_referential_follow_up(query: str) -> bool:
    """Allow short follow-ups to inherit context, but never map a new unknown name."""
    words = set(_normalize_product_text(query).split())
    follow_up_vocabulary = {
        "and", "also", "what", "about", "the", "price", "cost", "stock", "inventory",
        "availability", "available", "how", "much", "is", "it", "its", "do", "does", "we", "have",
        "et", "aussi", "quel", "quelle", "le", "la", "les", "prix", "stock", "combien",
        "disponible", "disponibilite", "est", "il", "elle", "son", "sa", "ses", "en", "reste",
    }
    return bool(words) and len(words) <= 8 and words.issubset(follow_up_vocabulary)


def _requested_inventory_fields(query: str) -> list[str]:
    normalized = _normalize_product_text(query)
    padded = f" {normalized} "
    price_terms = ("price", "unit price", "cost", "prix", "combien coute", "tarif")
    stock_terms = (
        "stock", "inventory", "available", "availability", "in stock", "units left",
        "quantity available", "en stock", "disponible", "disponibilite", "reste combien",
    )
    wants_stock = any(f" {_normalize_product_text(term)} " in padded for term in stock_terms)
    wants_price = any(f" {_normalize_product_text(term)} " in padded for term in price_terms)
    if " how much " in padded and not wants_stock:
        wants_price = True
    if wants_price and wants_stock:
        return ["unit_price", "available_stock"]
    if wants_price:
        return ["unit_price"]
    if wants_stock:
        return ["available_stock"]
    return ["unit_price", "available_stock"]


def _fallback_route(query: str) -> str:
    text = _normalize_product_text(query)
    padded = f" {text} "

    def has_any(phrases):
        return any(f" {_normalize_product_text(phrase)} " in padded for phrase in phrases)

    policy_terms = (
        "delivery policy", "delivery time", "shipping", "shipping policy", "return policy",
        "return", "refund", "warranty", "company policy", "commercial policy",
        "terms and conditions", "politique de livraison", "delai de livraison", "livraison",
        "politique de retour", "retour", "remboursement", "garantie", "conditions commerciales",
        "conditions generales", "payment terms", "payment methods", "paiement", "mode de paiement",
    )
    if has_any(policy_terms):
        return "knowledge"

    explicit_quote = has_any((
        "quote", "quotation", "prepare a quote", "request a quote", "devis", "faire un devis",
        "commander", "commande", "buy", "purchase", "order", "acheter", "je veux acheter",
    ))
    if explicit_quote:
        return "client_portal"

    wants_products = has_any((
        "i want", "i would like", "i need", "i'd like", "je veux", "je voudrais",
        "j'aimerais", "j aimerais", "j ai besoin", "i would need",
    ))
    quantity = re.search(
        r"\b(?:\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|"
        r"vingt|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
        text,
    )
    asks_current_data = has_any((
        "stock", "inventory", "price", "prix", "available", "availability", "catalogue", "catalog",
    ))
    if wants_products and quantity and not asks_current_data:
        return "client_portal"

    if has_any((
        "forecast", "forcast", "forest demand", "predict", "prediction", "demand", "future sales", "prevision", "previsions",
        "forecasting", "rupture", "rupture de stock", "stockout", "out of stock", "reorder",
        "restock", "replenish", "reapprovisionner", "reapprovisionnement", "demande future",
        "next week", "next month", "tomorrow", "will sell", "will we run out", "risk of shortage",
        "low stock", "running low", "near stockout", "la semaine prochaine", "le mois prochain",
        "demain", "va se vendre", "risque de rupture",
    )):
        return "forecast"

    if has_any((
        "stock", "inventory", "catalog", "catalogue", "products", "product", "produits", "produit",
        "price", "cost", "prix", "combien coute", "combien coûte", "available", "availability",
        "disponible", "disponibilite", "combien en stock", "liste des produits", "show all",
        "in stock", "on hand", "units left", "remaining", "how much left", "quantity available",
        "have any", "do you have", "still have", "en stock", "il reste", "reste combien",
    )):
        return "inventory"

    return "general"


def _supervisor(state: AgentState) -> dict:
    query = state["query"]
    normalized_query = _normalize_product_text(query)
    fallback = _fallback_route(query)
    if fallback == "knowledge":
        return {"route": "knowledge"}
    if normalized_query in {
        "hi", "hello", "hey", "bonjour", "salut", "bonsoir", "good morning",
        "good afternoon", "help", "aide", "what can you do", "que peux tu faire",
        "que pouvez vous faire", "thanks", "thank you", "merci", "ok", "okay",
    }:
        return {"route": "general"}

    if _wants_full_catalogue(query):
        return {"route": "inventory"}

    try:
        catalogue = list_catalogue(limit=100)
    except Exception:
        if fallback == "general":
            return {"route": "general"}
        raise
    current_mentions = _catalogue_mentions(query, catalogue)
    mentions = current_mentions
    context_query = query
    if not mentions and _is_referential_follow_up(query):
        for entry in reversed(state.get("history", [])[-10:]):
            if entry.get("role") != "user":
                continue
            prior_query = str(entry.get("content", ""))
            prior_mentions = _catalogue_mentions(prior_query, catalogue)
            if prior_mentions:
                mentions = prior_mentions
                context_query = f"{prior_query}\nFollow-up question: {query}"
                break

    if fallback == "client_portal":
        return {"route": "client_portal"}
    if fallback == "forecast":
        return {
            "route": "forecast",
            "matched_products": [item["product_name"] for item in mentions],
            "context_query": context_query,
        }
    if fallback == "inventory" or current_mentions:
        return {
            "route": "inventory",
            "matched_products": [item["product_name"] for item in mentions],
            "context_query": context_query,
        }
    return {"route": "general", "context_query": context_query}


def _inventory_agent(state: AgentState) -> dict:
    query = state["query"]
    catalogue = list_catalogue(limit=100)
    show_catalogue = _wants_full_catalogue(query)
    if show_catalogue:
        hits = catalogue
        answer = f"Here are all {len(hits)} products in the current catalogue, with their current prices and stock."
    else:
        hits = _catalogue_mentions(query, catalogue)
        selected_names = set(state.get("matched_products", []))
        if selected_names:
            hits = [item for item in catalogue if item["product_name"] in selected_names]
        if not hits:
            answer = (
                "I couldn't match that product to the catalogue. Check the product name, or ask "
                "'Show all products' to see the catalogue."
            )
            return {"answer": answer, "details": {"products": []}, "sources": []}
        else:
            fields = _requested_inventory_fields(query)
            if fields == ["unit_price"]:
                answer = f"I found {len(hits)} matching product(s). Here is the current price."
            elif fields == ["available_stock"]:
                answer = f"I found {len(hits)} matching product(s). Here is the current stock."
            else:
                answer = f"I found {len(hits)} matching product(s). Here are the current prices and stock."
            hits = [
                {key: item[key] for key in ("product_name", *fields) if key in item}
                for item in hits
            ]
    return {"answer": answer, "details": {"products": hits}, "sources": []}


def _forecast_agent(state: AgentState) -> dict:
    catalogue = list_catalogue(limit=100)
    selected_names = state.get("matched_products", [])
    context_query = state.get("context_query", state["query"])
    matches = selected_names or [
        item["product_name"] for item in _catalogue_mentions(context_query, catalogue)
    ]
    if not matches:
        names = [item["product_name"] for item in catalogue]
        answer = "Tell me which product to estimate. I can check: " + ", ".join(names[:15])
        return {"answer": answer, "details": {"estimates": []}, "sources": []}
    raw_estimates = [forecast_product_demand(name) for name in matches]
    estimates = [
        {
            "product_name": item["product_name"],
            "estimated_next_7_day_demand": item["estimated_next_7_day_demand"],
        }
        for item in raw_estimates
        if item.get("estimated_next_7_day_demand") is not None
    ]
    without_history = [
        item["product_name"] for item in raw_estimates
        if item.get("estimated_next_7_day_demand") is None
    ]
    if not estimates:
        return {
            "answer": "There is not enough recent sales history to estimate demand for "
            + ", ".join(without_history) + ".",
            "details": {"estimates": []},
            "sources": [],
        }
    answer = "Estimated demand for the next 7 days, based on recent sales."
    if without_history:
        answer += " No estimate is available for: " + ", ".join(without_history) + "."
    return {
        "answer": answer,
        "details": {"estimates": estimates},
        "sources": [],
    }


def _client_portal_agent(state: AgentState) -> dict:
    return {
        "answer": (
            "Quotation requests are submitted by clients from Client Mode. "
            "Please ask the customer to sign in to the client portal and create the request there."
        ),
        "details": {},
        "sources": [],
    }


def _knowledge_agent(state: AgentState) -> dict:
    result = answer_from_knowledge(state["query"])
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "details": {"retrieval_mode": result["retrieval_mode"]},
    }


def _general_agent(state: AgentState) -> dict:
    query = state["query"].strip()
    normalized = _normalize_product_text(query)
    greetings = {
        "hi", "hello", "hey", "bonjour", "salut", "bonsoir", "good morning", "good afternoon",
    }
    if normalized in greetings:
        answer = "Hello! I can help with product prices, stock, demand forecasts, and documented business policies."
    elif normalized in {"help", "aide", "what can you do", "que peux tu faire", "que pouvez vous faire"}:
        answer = (
            "I can check product prices and stock, show the catalogue, estimate demand, and search approved "
            "company documents. Quote requests are submitted from Client Mode."
        )
    else:
        try:
            answer = chat([
                {
                    "role": "system",
                    "content": (
                        "You are AutoPilot AI, a helpful business assistant. Reply in the same language as the user, "
                        "concisely and clearly. For AutoPilot's prices, stock, forecasts, quotations, or company "
                        "policies, do not guess: say you need the connected catalogue, forecast, quote workflow, "
                        "or approved company documents. The catalogue contains only product names, prices, and stock; "
                        "do not invent technical specifications. Do not claim to have changed data or submitted a quotation."
                    ),
                },
                *state.get("history", [])[-6:],
                {"role": "user", "content": query},
            ], timeout=45)
        except Exception:
            answer = (
                "I can help with products, stock, forecasts, and approved company documents. "
                "The general AI service is currently unavailable; please try again when Ollama is running."
            )
    return {"answer": answer, "sources": [], "details": {}}


def _agent_for_route(state: AgentState) -> Literal["inventory", "forecast", "client_portal", "knowledge", "general"]:
    return state.get("route", "knowledge")


builder = StateGraph(AgentState)
builder.add_node("supervisor", _supervisor)
builder.add_node("inventory", _inventory_agent)
builder.add_node("forecast", _forecast_agent)
builder.add_node("client_portal", _client_portal_agent)
builder.add_node("knowledge", _knowledge_agent)
builder.add_node("general", _general_agent)
builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor",
    _agent_for_route,
    {route: route for route in ROUTES},
)
for specialist in ROUTES:
    builder.add_edge(specialist, END)

agent_graph = builder.compile()


def run_agent(query: str, history: list[dict] | None = None) -> dict:
    recorder = RunRecorder(query)
    route = _fallback_route(query)
    try:
        state = agent_graph.invoke({
            "query": query.strip(),
            "history": history or [],
        })
        route = state.get("route", "knowledge")
        result = {
            "route": route,
            "answer": state.get("answer", "I could not prepare a response."),
            "sources": state.get("sources", []),
            "details": state.get("details", {}),
        }
        recorder.finish(route=route, success=True, sources=len(result["sources"]))
        return result
    except Exception as error:
        recorder.finish(route=route, success=False, error=type(error).__name__)
        if error.__class__.__module__.startswith(("psycopg", "psycopg2")):
            answer = "I couldn't retrieve the business data. Check that PostgreSQL is running, then try again."
        elif route in {"inventory", "forecast"}:
            answer = "I couldn't retrieve catalogue or sales data. Check the PostgreSQL connection and try again."
        elif route == "knowledge":
            answer = "I couldn't search the approved company documents. Please try again shortly."
        else:
            answer = "I couldn't reach the AI service. Check that Ollama is running, then try again."
        return {"route": route, "answer": answer, "sources": [], "details": {}}

