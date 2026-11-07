"""Launch the Property Rescue evidence MCP server (stdio) for the pr-triage Codex agent.

Codex starts this with an absolute path, from any working directory:
    <repo>/.venv/bin/python <repo>/scripts/agent_evidence_mcp.py --mattermost-user-id ID --app-user-id UUID
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from property_rescue.agent_tools import main  # noqa: E402

main()
