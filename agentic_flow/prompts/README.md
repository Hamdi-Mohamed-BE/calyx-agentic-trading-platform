# Calyx agent prompts

These two prompts are packaged resources used to restore the Calyx operating context in a fresh agent session.

| Prompt | Purpose | Precedence |
|---|---|---|
| `CALYX_ACTIVE_EA_AND_RESEARCH_ROOT.md` | Canonical research, evidence, website, portfolio, audit, and governance behavior | Highest |
| `AGENT_MCP_SETUP_PROMPT.md` | Portable MCP/tool bootstrap and market-analysis operating checklist | Supplemental |

They are sanitized adaptations of the private operating documents. The public editions intentionally replace user-specific paths, broker/account identifiers, strategy identifiers, current portfolio roster, exact deployment details, and private artifact locations with interfaces or environment placeholders.

## Load from Python

```python
from agentic_flow.prompts import load_agent_context, load_prompt

canonical_context = load_agent_context()
context_with_bootstrap = load_agent_context(include_mcp_setup=True)
mcp_only = load_prompt("AGENT_MCP_SETUP_PROMPT.md")
```

`load_agent_context()` always places the canonical prompt first. Private runtime details must be injected separately from local, untracked configuration and must never be concatenated into logs or published outputs.

## Maintenance rule

Update the canonical prompt when governance, evidence schema, validation stages, deployment boundary, or portfolio controls change. Update the MCP prompt when supported tools or initialization patterns change. Do not hard-code performance figures, current account state, credentials, personal paths, or private strategy inventory in either file.

