"""
DataSoul — Model Context Protocol (MCP) Integration
======================================================
Connects to local stdio and remote SSE Model Context Protocol servers.
Enables listing tools/resources, executing them, and importing tabular output.
"""

import os
import sys
import json
import asyncio
import urllib.parse
import httpx
import pandas as pd
from typing import Optional, Dict, Any, List
from . import IntegrationBase

class MCPClient:
    """A generic, pure-Python client for Model Context Protocol (MCP) servers."""
    
    def __init__(self):
        self.transport_type = None  # "stdio" or "sse"
        self.proc = None
        self.client = None
        self.sse_url = None
        self.post_url = None
        self.request_id = 0
        self.pending_requests = {}
        self.logs = []
        self.listen_tasks = []
        self.connected_event = asyncio.Event()
        self.server_info = {}
        self.capabilities = {}
        self.is_connected = False

    async def connect_stdio(self, command: str, args: List[str]):
        """Connect to a local MCP server using a stdio subprocess."""
        self.transport_type = "stdio"
        self.logs.append(f"Launching local process: {command} {' '.join(args)}")
        
        try:
            if sys.platform == "win32":
                # On Windows, cmd /c or running in shell is required for npx/npm commands
                cmd_str = f'"{command}"' if " " in command else command
                if args:
                    cmd_str += " " + " ".join(args)
                self.proc = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
                self.proc = await asyncio.create_subprocess_exec(
                    command,
                    *args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
        except Exception as e:
            self.logs.append(f"Process spawn failed: {e}")
            raise Exception(f"Failed to start local MCP server: {e}")
            
        self.listen_tasks.append(asyncio.create_task(self._read_stdout_loop()))
        self.listen_tasks.append(asyncio.create_task(self._read_stderr_loop()))
        
        self.is_connected = True
        self.connected_event.set()
        await self.initialize()

    async def connect_sse(self, sse_url: str):
        """Connect to a remote or local MCP server using HTTP SSE."""
        self.transport_type = "sse"
        self.sse_url = sse_url
        self.logs.append(f"Connecting to SSE endpoint: {sse_url}")
        self.client = httpx.AsyncClient(timeout=30.0)
        
        self.listen_tasks.append(asyncio.create_task(self._read_sse_loop()))
        
        # Wait for endpoint address setup
        try:
            await asyncio.wait_for(self.connected_event.wait(), timeout=12.0)
        except asyncio.TimeoutError:
            await self.disconnect()
            raise TimeoutError("SSE connection established, but did not receive HTTP POST endpoint from server")
            
        self.is_connected = True
        await self.initialize()

    async def initialize(self):
        """Perform MCP Protocol handshake."""
        init_res = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": False},
                "sampling": {}
            },
            "clientInfo": {
                "name": "DataSoul",
                "version": "3.0.0"
            }
        })
        
        if "error" in init_res:
            raise Exception(f"Protocol initialization failed: {init_res['error']}")
            
        result = init_res.get("result", {})
        self.server_info = result.get("serverInfo", {})
        self.capabilities = result.get("capabilities", {})
        
        await self.send_notification("notifications/initialized")
        self.logs.append(f"Initialized server: {self.server_info.get('name', 'Unknown')} v{self.server_info.get('version', '0.0.0')}")

    async def send_request(self, method: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for the matching response."""
        self.request_id += 1
        req_id = self.request_id
        
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        
        event = asyncio.Event()
        self.pending_requests[req_id] = {"event": event, "response": None}
        
        if self.transport_type == "stdio":
            if not self.proc or not self.proc.stdin:
                raise Exception("Local process is not running")
            line = json.dumps(req) + "\n"
            self.proc.stdin.write(line.encode("utf-8"))
            await self.proc.stdin.drain()
        elif self.transport_type == "sse":
            if not self.client or not self.post_url:
                raise Exception("SSE client is not connected")
            try:
                res_http = await self.client.post(self.post_url, json=req)
                if res_http.status_code >= 400:
                    raise Exception(f"HTTP Error {res_http.status_code}: {res_http.text}")
            except Exception as e:
                self.pending_requests.pop(req_id, None)
                raise Exception(f"Failed to post JSON-RPC: {e}")
        else:
            raise Exception("Not connected to any transport")
            
        # Wait for response
        try:
            await asyncio.wait_for(event.wait(), timeout=15.0)
            return self.pending_requests[req_id]["response"]
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request '{method}' (id={req_id}) timed out after 15s")
        finally:
            self.pending_requests.pop(req_id, None)

    async def send_notification(self, method: str, params: Dict[str, Any] | None = None):
        """Send a JSON-RPC notification (no response expected)."""
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        line = json.dumps(req) + "\n"
        
        try:
            if self.transport_type == "stdio" and self.proc and self.proc.stdin:
                self.proc.stdin.write(line.encode("utf-8"))
                await self.proc.stdin.drain()
            elif self.transport_type == "sse" and self.client and self.post_url:
                await self.client.post(self.post_url, json=req)
        except Exception as e:
            print(f"[MCP Client] Failed to send notification: {e}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools exposed by the MCP server."""
        res = await self.send_request("tools/list")
        return res.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        res = await self.send_request("tools/call", {"name": name, "arguments": arguments})
        if "error" in res:
            return {"error": res["error"]}
        return res.get("result", {})

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List all resources exposed by the MCP server."""
        res = await self.send_request("resources/list")
        return res.get("result", {}).get("resources", [])

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource from the MCP server."""
        res = await self.send_request("resources/read", {"uri": uri})
        if "error" in res:
            return {"error": res["error"]}
        return res.get("result", {})

    async def disconnect(self):
        """Clean up process/connection and stop all background tasks."""
        self.is_connected = False
        self.logs.append("Disconnecting from MCP server...")
        
        for task in self.listen_tasks:
            task.cancel()
            
        self.listen_tasks.clear()
        
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except Exception:
                pass
            self.proc = None
            
        if self.client:
            try:
                await self.client.aclose()
            except Exception:
                pass
            self.client = None
            
        self.post_url = None
        self.logs.append("Disconnected successfully")

    # --- Background Read Loops ---

    async def _read_stdout_loop(self):
        while True:
            try:
                if not self.proc or not self.proc.stdout:
                    break
                line_bytes = await self.proc.stdout.readline()
                if not line_bytes:
                    break
                    
                line = line_bytes.decode("utf-8").strip()
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    # Capture non-JSON prints for logs/debugging
                    self.logs.append(f"[Server Stdout]: {line}")
                    continue
                    
                if "id" in data:
                    req_id = data["id"]
                    if req_id in self.pending_requests:
                        self.pending_requests[req_id]["response"] = data
                        self.pending_requests[req_id]["event"].set()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logs.append(f"Read stdout loop exception: {e}")
                break

    async def _read_stderr_loop(self):
        while True:
            try:
                if not self.proc or not self.proc.stderr:
                    break
                line_bytes = await self.proc.stderr.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8").strip()
                if line:
                    self.logs.append(f"[Server Stderr]: {line}")
                    if len(self.logs) > 300:
                        self.logs.pop(0)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def _read_sse_loop(self):
        current_event = None
        try:
            async with self.client.stream("GET", self.sse_url) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        
                        if current_event == "endpoint":
                            self.post_url = urllib.parse.urljoin(self.sse_url, data_str)
                            self.connected_event.set()
                        elif current_event == "message":
                            try:
                                data = json.loads(data_str)
                                if "id" in data:
                                    req_id = data["id"]
                                    if req_id in self.pending_requests:
                                        self.pending_requests[req_id]["response"] = data
                                        self.pending_requests[req_id]["event"].set()
                            except Exception as e:
                                print(f"[MCP SSE] Message decode error: {e}")
                                
                        current_event = None
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logs.append(f"SSE loop connection lost: {e}")
            self.connected_event.set() # Unblock waiters on crash


class MCPIntegration(IntegrationBase):
    """DataSoul Integration class wrapping the MCP Client."""
    
    name = "mcp"
    display_name = "MCP Server"
    icon = "🔌"
    supports_import = True
    supports_export = False
    
    def __init__(self):
        # A dictionary mapping connection IDs to active MCPClient instances
        self.active_clients: Dict[str, MCPClient] = {}

    def get_client(self, connection_id: str) -> Optional[MCPClient]:
        """Retrieve an active client by connection ID."""
        return self.active_clients.get(connection_id)

    async def connect_client(self, config: Dict[str, Any]) -> str:
        """Create a new client connection based on type."""
        conn_id = config.get("connection_id") or os.urandom(4).hex()
        client = MCPClient()
        
        transport = config.get("transport")
        if transport == "stdio":
            cmd = config.get("command", "")
            args = config.get("args", [])
            if not cmd:
                raise ValueError("Command required for Stdio connection")
            await client.connect_stdio(cmd, args)
        elif transport == "sse":
            url = config.get("url", "")
            if not url:
                raise ValueError("SSE URL required for SSE connection")
            await client.connect_sse(url)
        else:
            raise ValueError(f"Unsupported transport type: {transport}")
            
        self.active_clients[conn_id] = client
        return conn_id

    async def disconnect_client(self, connection_id: str):
        """Disconnect and remove a client from the registry."""
        client = self.active_clients.pop(connection_id, None)
        if client:
            await client.disconnect()

    def validate_credentials(self, credentials: dict) -> dict:
        """Standard credential validator interface. Unused for direct dynamic connects."""
        return {"valid": True, "message": "MCP Connection verified dynamically"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """
        Parses tool call results or resource content into a DataFrame.
        This is synchronous but wrapped. In practice, the backend will call the direct JSON helpers,
        but this provides the mandatory IntegrationBase compatibility.
        """
        import_type = kwargs.get("import_type", "raw")
        raw_content = kwargs.get("content", "")
        
        if not raw_content:
            raise ValueError("No data content provided to import")
            
        # Parse CSV strings or JSON structures
        if isinstance(raw_content, str):
            clean_str = raw_content.strip()
            if clean_str.startswith("[") or clean_str.startswith("{"):
                try:
                    data = json.loads(clean_str)
                    return self._json_to_df(data)
                except Exception:
                    pass
            # Fallback to CSV loading
            try:
                from io import StringIO
                return pd.read_csv(StringIO(clean_str), low_memory=False)
            except Exception as e:
                raise ValueError(f"Failed to parse text as CSV or JSON: {e}")
        elif isinstance(raw_content, (list, dict)):
            return self._json_to_df(raw_content)
            
        raise ValueError(f"Unsupported data format: {type(raw_content)}")

    def _json_to_df(self, json_data: Any) -> pd.DataFrame:
        """Helper to convert various JSON responses into a clean DataFrame."""
        if isinstance(json_data, list):
            # Array of objects
            return pd.DataFrame(json_data)
        elif isinstance(json_data, dict):
            # Check if there is a list key (e.g. "records", "data", "rows")
            for key in ["records", "data", "rows", "results", "items"]:
                if key in json_data and isinstance(json_data[key], list):
                    return pd.DataFrame(json_data[key])
            # Just a single object
            return pd.DataFrame([json_data])
        return pd.DataFrame()

    def get_status(self) -> dict:
        status = super().get_status()
        status["available"] = True
        status["active_connections"] = len(self.active_clients)
        return status
