# IBM Orchestrate setup for real-company research

The InvestIQ API can send one company's validated evidence to an IBM watsonx
Orchestrate agent. The agent calls **two tools** and writes the research
summary. It retrieves nothing itself; the application gathers the evidence from
your local Moomoo OpenD gateway.

| Piece | File | Purpose |
|---|---|---|
| Tool 1 | `tools/powerpuffmen_snapshot_screen.py` | Four-rule snapshot screen (already imported) |
| Tool 2 | `tools/powerpuffmen_trend_check.py` | Three price-trend rules on supplied averages |
| Agent | `agents/investiq_research_agent.yaml` | Calls both tools, then summarises |
| Adapter | `frontend/agent_research.py` | Builds the evidence message, calls the agent |

The older `powerpuffmen_snapshot_agent` is unchanged and stays limited to
synthetic examples. A new agent is used so the existing one keeps working.

## 1. Import the tool and the agent

Use the same environment you used before (for example, in IBM Bob's terminal or
a PowerShell with the `orchestrate` CLI available and logged in):

    orchestrate tools import -k python -f tools/powerpuffmen_trend_check.py
    orchestrate agents import -f agents/investiq_research_agent.yaml
    orchestrate agents list -k native -v

Copy the **id** of `investiq_research_agent` from the list.

## 2. Test the agent in the Orchestrate chat first

Open the agent in the Orchestrate UI and use the starter prompt
"Research with unavailable net profit". In the trace, check that both
`powerpuffmen_snapshot_screen` and `powerpuffmen_trend_check` were called.

## 3. Configure the API window (never in files or Git)

In the PowerShell window that runs the API, before starting uvicorn:

    $credential = Get-Credential -UserName "apikey" -Message "Paste your IBM WXO API key into the Password field"
    $env:WXO_API_KEY = $credential.GetNetworkCredential().Password
    Remove-Variable credential
    $env:WXO_RESEARCH_AGENT_ID = "<the id from step 1>"

Optional: `$env:WXO_BASE_URL = "<your Orchestrate instance URL>"`. The default is
the instance already used by this project.

## What is sent, and when

Only when you press **Ask the IBM agent** in the UI. The message contains the
ticker, company name, timestamps, the validated screening inputs and price
measures, and which values are withheld. It is shown in the UI under "Data sent
to the agent". It never contains your API key.

## Evidence that the tools ran

The UI shows the run and trace ids returned by Orchestrate, and whether the
reply contains each tool's version string (`snapshot-net-profit-volume-v2`,
`trend-check-v1`). That string check is weak. **The Orchestrate trace is the
proof**: open it and confirm both tool calls before claiming orchestration.

## Using IBM Bob

The repository includes Bob skills (`.bob/skills`). Two are directly useful:
`agent-instructions-evaluator` on `agents/investiq_research_agent.yaml`, and
`wxo-builder` for changing the agent or tools. Describe in your submission
exactly what Bob built or reviewed.
