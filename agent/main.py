"""Compatibility entrypoint; the canonical API and graph live in agent.server/agent.graph."""
from agent.server import app

__all__ = ["app"]
