"""MCP entrypoint for compatible AI hosts; bind to localhost by default."""
import json

from mcp.server.fastmcp import FastMCP

from .services.business_tools import (
    forecast_product_demand,
    get_product_stock,
    list_catalogue,
)

mcp = FastMCP("AutoPilot AI V2")


@mcp.tool()
def search_products(search: str = "", limit: int = 30) -> str:
    """Search the current product catalogue and return price and available stock."""
    return json.dumps(list_catalogue(search=search, limit=limit), ensure_ascii=False)


@mcp.tool()
def check_product_stock(product_name: str) -> str:
    """Read the current stock and unit price of one exact catalogue product."""
    return json.dumps(get_product_stock(product_name), ensure_ascii=False)


@mcp.tool()
def estimate_product_demand(product_name: str, days: int = 30) -> str:
    """Estimate next-week demand from recent approved sales; does not alter stock."""
    return json.dumps(forecast_product_demand(product_name, days), ensure_ascii=False)


@mcp.resource("autopilot://catalogue")
def catalogue_resource() -> str:
    """Read-only snapshot of the current catalogue."""
    return json.dumps(list_catalogue(limit=100), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8003,
        stateless_http=True,
        json_response=True,
    )

