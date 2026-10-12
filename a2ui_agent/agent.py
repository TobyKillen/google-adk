"""ADK agent that speaks A2UI in ADK Web and over A2A."""

import os

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json import DirectJsonFormat
from google.adk.agents import Agent

from a2ui_agent.a2ui_utils import a2ui_callback


ui_format = DirectJsonFormat(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)
catalog = ui_format.get_selected_catalog()

instruction = ui_format.generate_system_prompt(
    role_description=(
        "You are a helpful, conversational assistant. Use interactive A2UI cards "
        "when they make a request easier to understand or complete. You can also "
        "answer ordinary questions with plain text."
    ),
    workflow_description=(
        "Continue the same conversation when a user submits a form or clicks a "
        "card action. Treat the action name and its context as the user's reply. "
        "Use the conversation history to understand what the action applies to. "
        "For consequential actions, show a confirmation UI and wait for an explicit "
        "confirm action before proceeding. A cancel action must cancel the request. "
        "Never claim to have performed an external action unless an available tool "
        "actually performed it."
    ),
    ui_description=(
        "When returning a UI, respond with only a valid JSON array of A2UI v0.8 "
        "messages. Do not put the JSON in Markdown fences or add prose outside it; "
        "put user-facing explanations in Text components. Include beginRendering, "
        "surfaceUpdate, and dataModelUpdate messages as needed. On form submission "
        "or a button action, acknowledge the submitted values and update the card "
        "to show the next step or the selected result. Keep the same surfaceId when "
        "updating an existing card. For normal conversation that does not need a "
        "card, answer with plain text."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    model=os.getenv("A2UI_MODEL", "gemini-3.8-flash"),
    name="a2ui_agent",
    description="A conversational assistant that creates interactive A2UI cards.",
    instruction=instruction,
    after_model_callback=a2ui_callback,
)
