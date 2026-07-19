import sys
import httpx
from fastmcp import FastMCP

BASE_URL = "http://localhost:8086/api"

try:
    spec = httpx.get(f"{BASE_URL}/openapi.json", timeout=10).json()
except httpx.RequestError as e:
    sys.exit(f"Cannot reach mydiary backend at {BASE_URL}: {e}")

mcp = FastMCP.from_openapi(
    openapi_spec=spec,
    client=httpx.AsyncClient(base_url=BASE_URL),
    name="mydiary",
)

if __name__ == "__main__":
    mcp.run()
