"""
Odoo MCP Server — Gold Tier

Exposes Odoo 17 Community accounting & CRM capabilities to Claude Code via MCP tools.
Uses Odoo's JSON-RPC 2.0 external API.

Tools exposed:
  - odoo_list_invoices      : list customer invoices (draft/posted/paid)
  - odoo_create_invoice     : create a customer invoice
  - odoo_post_invoice       : confirm/post a draft invoice
  - odoo_get_invoice        : get invoice details by ID
  - odoo_list_customers     : list customers/partners
  - odoo_create_customer    : create a new customer
  - odoo_list_products      : list products/services
  - odoo_get_accounting_summary : get monthly P&L summary
  - odoo_list_expenses      : list vendor bills / expenses
  - odoo_search_records     : generic model search

Prerequisites:
  1. Odoo running: cd odoo && docker compose up -d
  2. Install: pip install mcp requests
  3. Set env vars: ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

Add to Claude Code settings:
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_servers/odoo_mcp/server.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "odoo",
        "ODOO_USERNAME": "admin",
        "ODOO_PASSWORD": "admin"
      }
    }
  }
}
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import Tool, TextContent, CallToolResult
except ImportError:
    print("ERROR: mcp not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ── config ─────────────────────────────────────────────────────────────────────
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASS = os.getenv("ODOO_PASSWORD", "admin")
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

VAULT_PATH = Path(os.getenv("VAULT_PATH", Path(__file__).parent.parent.parent / "AI_Employee_Vault"))
LOGS_DIR = VAULT_PATH / "Logs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [OdooMCP] %(levelname)s: %(message)s")
logger = logging.getLogger("OdooMCP")


# ── Odoo JSON-RPC client ────────────────────────────────────────────────────────

class OdooClient:
    def __init__(self):
        self._uid: int | None = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _rpc(self, endpoint: str, method: str, params: dict) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": params,
        }
        resp = self._session.post(f"{ODOO_URL}{endpoint}", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Odoo RPC error: {data['error']}")
        return data.get("result")

    def authenticate(self) -> int:
        if self._uid is None:
            uid = self._rpc("/web/dataset/call_kw", "call", {
                "service": "common",
                "method": "authenticate",
                "args": [ODOO_DB, ODOO_USER, ODOO_PASS, {}],
            })
            # Odoo 17 uses /web/session/authenticate
            result = self._rpc("/web/session/authenticate", "call", {
                "db": ODOO_DB,
                "login": ODOO_USER,
                "password": ODOO_PASS,
            })
            self._uid = result.get("uid") if isinstance(result, dict) else None
            if not self._uid:
                # fallback: xmlrpc-like authenticate
                uid_result = self._rpc("/web/dataset/call_kw", "call", {
                    "model": "res.users",
                    "method": "search",
                    "args": [[["login", "=", ODOO_USER]]],
                    "kwargs": {"limit": 1},
                })
                self._uid = uid_result[0] if uid_result else 1
        return self._uid

    def execute(self, model: str, method: str, args: list, kwargs: dict = None) -> Any:
        self.authenticate()
        return self._rpc("/web/dataset/call_kw", "call", {
            "model": model,
            "method": method,
            "args": args,
            "kwargs": kwargs or {},
        })

    def search_read(self, model: str, domain: list, fields: list, limit: int = 50, offset: int = 0) -> list:
        return self.execute(model, "search_read", [domain], {
            "fields": fields,
            "limit": limit,
            "offset": offset,
        })

    def create(self, model: str, values: dict) -> int:
        return self.execute(model, "create", [values])

    def write(self, model: str, ids: list, values: dict) -> bool:
        return self.execute(model, "write", [ids, values])


_client = OdooClient()


def _log_action(action_type: str, details: dict, result: str = "success"):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{date.today().isoformat()}.json"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "odoo_mcp",
        "details": details,
        "result": result,
    }
    existing = []
    if log_file.exists():
        try:
            existing = json.loads(log_file.read_text())
        except Exception:
            existing = []
    existing.append(entry)
    log_file.write_text(json.dumps(existing, indent=2))


# ── MCP server setup ────────────────────────────────────────────────────────────

server = Server("odoo-mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="odoo_list_invoices",
            description="List customer invoices from Odoo. Filter by state: draft, posted, paid, cancel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["draft", "posted", "paid", "cancel", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 20},
                    "customer_name": {"type": "string", "description": "Filter by customer name (partial match)"},
                },
            },
        ),
        Tool(
            name="odoo_get_invoice",
            description="Get detailed information about a specific invoice by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "integer", "description": "Odoo invoice ID"},
                },
                "required": ["invoice_id"],
            },
        ),
        Tool(
            name="odoo_create_invoice",
            description="Create a new customer invoice in Odoo (as draft). Requires approval before posting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "customer_email": {"type": "string"},
                    "lines": {
                        "type": "array",
                        "description": "Invoice line items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_name": {"type": "string"},
                                "quantity": {"type": "number"},
                                "price_unit": {"type": "number"},
                                "description": {"type": "string"},
                            },
                            "required": ["quantity", "price_unit"],
                        },
                    },
                    "notes": {"type": "string", "description": "Internal notes"},
                },
                "required": ["customer_name", "lines"],
            },
        ),
        Tool(
            name="odoo_post_invoice",
            description="Post (confirm) a draft invoice in Odoo. This is irreversible — requires prior human approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "integer"},
                    "approval_file": {"type": "string", "description": "Path to the approval file in /Approved/"},
                },
                "required": ["invoice_id", "approval_file"],
            },
        ),
        Tool(
            name="odoo_list_customers",
            description="List customers/partners in Odoo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Name or email search term"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="odoo_create_customer",
            description="Create a new customer/partner in Odoo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "company_name": {"type": "string"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="odoo_list_products",
            description="List products/services in Odoo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {"type": "string"},
                    "limit": {"type": "integer", "default": 30},
                },
            },
        ),
        Tool(
            name="odoo_get_accounting_summary",
            description="Get monthly accounting summary: total invoiced, paid, outstanding, and top customers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "YYYY-MM format, defaults to current month"},
                },
            },
        ),
        Tool(
            name="odoo_list_expenses",
            description="List vendor bills / expenses in Odoo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["draft", "posted", "paid", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="odoo_search_records",
            description="Generic search on any Odoo model. Use for advanced queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "e.g. account.move, res.partner, product.product"},
                    "domain": {"type": "array", "description": "Odoo domain filter, e.g. [[\"state\",\"=\",\"posted\"]]"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["model", "fields"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        result = await _dispatch(name, arguments)
        _log_action(name, arguments, "success")
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        _log_action(name, arguments, f"error: {e}")
        logger.error(f"Tool {name} failed: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict) -> Any:
    if name == "odoo_list_invoices":
        return _list_invoices(args)
    elif name == "odoo_get_invoice":
        return _get_invoice(args["invoice_id"])
    elif name == "odoo_create_invoice":
        return _create_invoice(args)
    elif name == "odoo_post_invoice":
        return _post_invoice(args)
    elif name == "odoo_list_customers":
        return _list_customers(args)
    elif name == "odoo_create_customer":
        return _create_customer(args)
    elif name == "odoo_list_products":
        return _list_products(args)
    elif name == "odoo_get_accounting_summary":
        return _get_accounting_summary(args)
    elif name == "odoo_list_expenses":
        return _list_expenses(args)
    elif name == "odoo_search_records":
        return _search_records(args)
    else:
        raise ValueError(f"Unknown tool: {name}")


def _list_invoices(args: dict) -> dict:
    state = args.get("state", "all")
    limit = args.get("limit", 20)
    customer_name = args.get("customer_name", "")

    domain = [["move_type", "=", "out_invoice"]]
    if state != "all":
        domain.append(["payment_state" if state == "paid" else "state", "=", state])
    if customer_name:
        domain.append(["partner_id.name", "ilike", customer_name])

    records = _client.search_read(
        "account.move", domain,
        ["name", "partner_id", "amount_total", "state", "payment_state", "invoice_date", "invoice_date_due"],
        limit=limit,
    )
    return {"count": len(records), "invoices": records}


def _get_invoice(invoice_id: int) -> dict:
    records = _client.search_read(
        "account.move", [["id", "=", invoice_id]],
        ["name", "partner_id", "amount_total", "amount_residual", "state", "payment_state",
         "invoice_date", "invoice_date_due", "invoice_line_ids", "narration"],
    )
    if not records:
        return {"error": f"Invoice {invoice_id} not found"}
    inv = records[0]
    # fetch lines
    lines = _client.search_read(
        "account.move.line",
        [["move_id", "=", invoice_id], ["display_type", "=", "product"]],
        ["name", "quantity", "price_unit", "price_subtotal"],
    )
    inv["lines"] = lines
    return inv


def _create_invoice(args: dict) -> dict:
    if DRY_RUN:
        return {"dry_run": True, "message": "DRY RUN: invoice not created", "args": args}

    # Find or create partner
    customer_name = args["customer_name"]
    partners = _client.search_read(
        "res.partner", [["name", "ilike", customer_name]],
        ["id", "name"], limit=1,
    )
    if partners:
        partner_id = partners[0]["id"]
    else:
        partner_vals = {"name": customer_name, "customer_rank": 1}
        if args.get("customer_email"):
            partner_vals["email"] = args["customer_email"]
        partner_id = _client.create("res.partner", partner_vals)

    # Build invoice lines
    line_commands = []
    for line in args.get("lines", []):
        line_vals = {
            "name": line.get("description") or line.get("product_name", "Service"),
            "quantity": line["quantity"],
            "price_unit": line["price_unit"],
        }
        if line.get("product_name"):
            products = _client.search_read(
                "product.product", [["name", "ilike", line["product_name"]]],
                ["id"], limit=1,
            )
            if products:
                line_vals["product_id"] = products[0]["id"]
        line_commands.append((0, 0, line_vals))

    invoice_vals = {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "invoice_line_ids": line_commands,
        "narration": args.get("notes", ""),
    }
    invoice_id = _client.create("account.move", invoice_vals)
    return {"success": True, "invoice_id": invoice_id, "partner_id": partner_id, "status": "draft"}


def _post_invoice(args: dict) -> dict:
    approval_file = Path(args.get("approval_file", ""))
    if not approval_file.exists():
        return {"error": f"Approval file not found: {approval_file}. Move to /Approved first."}

    if DRY_RUN:
        return {"dry_run": True, "message": "DRY RUN: invoice not posted"}

    invoice_id = args["invoice_id"]
    _client.execute("account.move", "action_post", [[invoice_id]])
    return {"success": True, "invoice_id": invoice_id, "status": "posted"}


def _list_customers(args: dict) -> dict:
    domain = [["customer_rank", ">", 0]]
    if args.get("search"):
        domain.append(["name", "ilike", args["search"]])
    records = _client.search_read(
        "res.partner", domain,
        ["name", "email", "phone", "city", "customer_rank"],
        limit=args.get("limit", 20),
    )
    return {"count": len(records), "customers": records}


def _create_customer(args: dict) -> dict:
    if DRY_RUN:
        return {"dry_run": True, "message": "DRY RUN: customer not created"}
    vals = {"name": args["name"], "customer_rank": 1}
    for field in ["email", "phone"]:
        if args.get(field):
            vals[field] = args[field]
    if args.get("company_name"):
        vals["company_name"] = args["company_name"]
    partner_id = _client.create("res.partner", vals)
    return {"success": True, "customer_id": partner_id}


def _list_products(args: dict) -> dict:
    domain = [["active", "=", True]]
    if args.get("search"):
        domain.append(["name", "ilike", args["search"]])
    records = _client.search_read(
        "product.product", domain,
        ["name", "list_price", "type", "categ_id"],
        limit=args.get("limit", 30),
    )
    return {"count": len(records), "products": records}


def _get_accounting_summary(args: dict) -> dict:
    month_str = args.get("month", date.today().strftime("%Y-%m"))
    try:
        year, month = map(int, month_str.split("-"))
    except ValueError:
        return {"error": "Invalid month format. Use YYYY-MM"}

    date_start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        date_end = f"{year+1:04d}-01-01"
    else:
        date_end = f"{year:04d}-{month+1:02d}-01"

    # Customer invoices
    invoices = _client.search_read(
        "account.move",
        [["move_type", "=", "out_invoice"], ["invoice_date", ">=", date_start], ["invoice_date", "<", date_end]],
        ["name", "partner_id", "amount_total", "amount_residual", "state", "payment_state"],
        limit=200,
    )
    total_invoiced = sum(r["amount_total"] for r in invoices)
    total_paid = sum(r["amount_total"] - r["amount_residual"] for r in invoices)
    total_outstanding = sum(r["amount_residual"] for r in invoices)

    # Vendor bills
    bills = _client.search_read(
        "account.move",
        [["move_type", "=", "in_invoice"], ["invoice_date", ">=", date_start], ["invoice_date", "<", date_end]],
        ["name", "partner_id", "amount_total", "state"],
        limit=200,
    )
    total_expenses = sum(r["amount_total"] for r in bills)

    return {
        "month": month_str,
        "revenue": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "invoice_count": len(invoices),
        },
        "expenses": {
            "total_expenses": total_expenses,
            "bill_count": len(bills),
        },
        "net_profit_estimate": total_paid - total_expenses,
        "invoices": invoices[:10],
    }


def _list_expenses(args: dict) -> dict:
    state = args.get("state", "all")
    domain = [["move_type", "=", "in_invoice"]]
    if state != "all":
        domain.append(["state", "=", state])
    records = _client.search_read(
        "account.move", domain,
        ["name", "partner_id", "amount_total", "state", "invoice_date"],
        limit=args.get("limit", 20),
    )
    return {"count": len(records), "expenses": records}


def _search_records(args: dict) -> dict:
    records = _client.search_read(
        args["model"],
        args.get("domain", []),
        args["fields"],
        limit=args.get("limit", 20),
    )
    return {"count": len(records), "records": records}


# ── entry point ────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
