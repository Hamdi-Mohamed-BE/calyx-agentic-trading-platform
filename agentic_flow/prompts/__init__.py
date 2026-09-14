"""Versioned, public-safe operating prompts for the Calyx agentic flow."""

from __future__ import annotations

from importlib.resources import files


MASTER_PROMPT = "CALYX_ACTIVE_EA_AND_RESEARCH_ROOT.md"
MCP_SETUP_PROMPT = "AGENT_MCP_SETUP_PROMPT.md"


def load_prompt(name: str = MASTER_PROMPT) -> str:
    """Return a packaged Calyx prompt by its exact public filename."""
    if name not in {MASTER_PROMPT, MCP_SETUP_PROMPT}:
        raise ValueError(f"Unknown Calyx prompt: {name}")
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


def load_agent_context(*, include_mcp_setup: bool = False) -> str:
    """Build the canonical agent context, optionally followed by MCP bootstrap help."""
    master = load_prompt(MASTER_PROMPT)
    if not include_mcp_setup:
        return master
    return f"{master}\n\n---\n\n{load_prompt(MCP_SETUP_PROMPT)}"

