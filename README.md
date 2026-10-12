# Conversational A2UI agent with Google ADK

This project runs the agent directly in ADK Web, where its built-in A2UI renderer
displays cards and routes card actions into the active chat session through a
small compatibility patch. The same agent can also be exposed as an A2A service
for clients such as Gemini Enterprise (GE).

The ADK Web bridge follows the [A2UI Quickstart](https://a2ui.org/quickstart/)
rendering approach: the agent generates A2UI v0.8 JSON, and an `after_model`
callback wraps each message in the `<a2a_datapart_json>` envelope recognized by
ADK Web. The A2A service converts those messages to A2UI DataParts for protocol
clients.

## Bare minimum: run in ADK Web

You need Python 3.10 or newer, a Gemini API key, and network access to the
selected Gemini model. No Node.js installation or separate frontend server is
needed.

From the project root, create the environment and install the pinned ADK and
protocol dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Configure Gemini in the same terminal. Get the key from Google AI Studio:

```bash
export GOOGLE_API_KEY="your-api-key"
```

Apply the ADK Web button-action patch, then start ADK Web:

```bash
python scripts/patch_adk_web_a2ui.py
adk web .
```

Open the URL printed by ADK, select `a2ui_agent`, and start a session. The patch
is required for card button clicks to return to the current chat. It targets
`google-adk==2.11.0` as pinned in `requirements.txt`; rerun it after reinstalling
that package. It is safe to run more than once.

To use another model, set `A2UI_MODEL` before starting ADK Web:

```bash
export A2UI_MODEL="your-supported-model"
```

Alternatively, use Vertex AI Application Default Credentials instead of an AI
Studio key:

```bash
gcloud auth application-default login
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="global"
```

Try this prompt:

> Create an interactive contact form with name and email fields, a product updates checkbox, and a Submit button. After I submit it, show me the values in a confirmation card with Confirm and Cancel buttons. Do not send or save anything. When I choose either option, acknowledge my choice in this conversation and update the card.

Click Submit, Confirm, or Cancel to continue the conversation in the same ADK Web
session. The button action and its bound form values are sent back to the agent
as a user turn. Confirmation never authorizes external side effects unless the
agent has an actual tool for that operation.

## Expose the same agent over A2A

Run this in another terminal for A2A clients, including Gemini Enterprise:

```bash
source .venv/bin/activate
A2A_PUBLIC_URL="https://your-public-agent-host" \
uvicorn a2ui_agent.a2a_server:a2a_app --host 0.0.0.0 --port 8001
```

The service advertises the A2UI v0.8 Basic Catalog and emits A2UI DataParts. An
A2A client must send card actions back to the agent as A2UI client-to-server
DataParts and render response DataParts with an A2UI renderer. ADK Web does not
need this A2A service; it loads `a2ui_agent` directly. Set `A2A_PUBLIC_URL` to
the externally reachable HTTPS URL that Gemini Enterprise should use. `A2A_HOST`
and `A2A_PORT` can override the bind address and port; the `uvicorn` command
must use the same values.
