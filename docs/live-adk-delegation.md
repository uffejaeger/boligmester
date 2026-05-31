# Live ADK Delegation Verification

Issue #4 tracks proving that the Google ADK runtime delegates to the intended
specialist agents, not just that the mocked contract returns those agent names.

## Verification Command

Run the verifier from the repository root:

```bash
PYTHONPATH=src python3 scripts/verify_live_adk_delegation.py --stdout-json
```

With live credentials:

```bash
export GOOGLE_API_KEY=your_key_here
PYTHONPATH=src python3 scripts/verify_live_adk_delegation.py \
  --listing-url https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c \
  --buyer-profile-id solo_engineer \
  --stdout-json
```

The verifier writes a timestamped evidence file under `output/` by default. The
file records runtime imports, the root Google ADK agent tree, credential status,
and the captured ADK event trace.

## Current Local Evidence

Generated on 2026-05-31 from this workspace:

* `google-adk` version: `2.1.0`
* `google.adk.runners.Runner`: import succeeded
* `google.adk.sessions.InMemorySessionService`: import succeeded
* Root Google ADK agent: `buyer_committee`
* Root sub-agents:
  * `listing_agent`
  * `market_comps_agent`
  * `danish_credit_agent`
  * `negotiation_agent`
  * `red_team_agent`
* Startup validation: succeeded with placeholder credentials
* Live model execution: blocked because `GOOGLE_API_KEY` was not set
* Evidence status: `blocked_missing_credentials`

The previous runner import path expected `InMemorySessionService` from
`google.adk.runners`. In the installed `google-adk==2.1.0` runtime it is exposed
from `google.adk.sessions`, so startup validation would reject an otherwise
installed runtime before this fix.

## Delegation Evidence Shape

During a live run, `GoogleAdkAnalysisRunner` records every ADK event it receives.
The evidence includes:

* `author`: the ADK event author, usually the root agent or a delegated agent
* `transfer_to_agent`: explicit transfer target when ADK emits one
* `final_response`: whether the event is a final ADK response
* `text`: model text captured from the event content, if present
* `error_code` and `error_message`: runtime errors surfaced on the event
* `runtime_error`: runner-level timeout or exception if ADK fails before a
  usable event trace is produced

The verifier reports `verified` only when all expected sub-agents are observed
as event authors or transfer targets. It reports `delegation_incomplete` when the
live runtime finishes but one or more expected sub-agents are missing from the
event stream, and `runtime_failed` when the runner records a live ADK exception.

If `delegation_incomplete` appears, create follow-up implementation issues for
the missing agents or routing prompt changes before closing issue #4.
