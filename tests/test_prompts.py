from agentic_flow.prompts import (
    MASTER_PROMPT,
    MCP_SETUP_PROMPT,
    load_agent_context,
    load_prompt,
)


def test_packaged_prompts_load_and_define_precedence() -> None:
    master = load_prompt(MASTER_PROMPT)
    mcp = load_prompt(MCP_SETUP_PROMPT)
    combined = load_agent_context(include_mcp_setup=True)

    assert "canonical operating prompt" in master
    assert "companion prompt" in mcp
    assert combined.startswith(master)
    assert combined.endswith(mcp)


def test_public_prompts_do_not_embed_private_identifiers() -> None:
    combined = load_agent_context(include_mcp_setup=True).lower()
    forbidden = (
        "c:\\users\\hama",
        "mcp_" "token=",
        "password=",
        "api_key=",
        "expected account:",
    )

    assert not any(value in combined for value in forbidden)
