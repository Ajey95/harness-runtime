"""
Minimal LangGraph integration scaffold.
This adapter provides a tiny runtime graph API to register steps and
execute them in order. It's intentionally lightweight and does not
pull external LangGraph dependencies; it provides a compatibility
layer so the rest of the runtime can connect to a graph-based API.
"""
from typing import Callable, Dict, List, Any
import inspect
import asyncio


class LangGraphAdapter:
    def __init__(self):
        self.nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        # Node `fn` may be sync or async; store as-is and detect at run-time.
        self.nodes[name] = fn
        self.edges.setdefault(name, [])

    def add_edge(self, src: str, dst: str):
        self.edges.setdefault(src, []).append(dst)

    async def _maybe_call(self, fn: Callable, ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if inspect.iscoroutinefunction(fn):
                return await fn(ctx) or ctx
            res = fn(ctx)
            if inspect.isawaitable(res):
                return await res or ctx
            return res or ctx
        except Exception as e:
            ctx.setdefault("errors", []).append({"node": getattr(fn, "__name__", "<node>"), "error": str(e)})
            return ctx

    async def run(self, start: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a simple async depth-first traversal executing node functions.
        Node functions may be sync or async and should accept/return the
        execution context dictionary.
        """
        visited = set()

        async def _run_node(n: str, ctx: Dict[str, Any]):
            if n in visited:
                return ctx
            visited.add(n)
            fn = self.nodes.get(n)
            if fn:
                ctx = await self._maybe_call(fn, ctx)
            for nxt in self.edges.get(n, []):
                ctx = await _run_node(nxt, ctx)
            return ctx

        return await _run_node(start, context)


# module-level singleton for convenience
adapter = LangGraphAdapter()
