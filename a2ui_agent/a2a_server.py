"""Expose the A2UI ADK agent over the A2A protocol."""

import json
import os
from typing import Any

from a2a.types import AgentCapabilities, AgentCard, AgentSkill, Part
from a2ui.a2a.extension import get_a2ui_agent_extension
from a2ui.a2a.parts import get_a2ui_datapart
from a2ui.adk.a2a.part_converter import A2uiPartConverter
from google.adk.a2a.converters.event_converter import convert_event_to_a2a_events
from google.adk.a2a.converters.part_converter import convert_a2a_part_to_genai_part
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.executor.config import A2aAgentExecutorConfig
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.genai import types

from a2ui_agent.agent import catalog, root_agent
from a2ui_agent.a2ui_utils import unwrap_adk_web_part


A2A_HOST = os.getenv("A2A_HOST", "127.0.0.1")
A2A_PORT = int(os.getenv("A2A_PORT", "8001"))
A2A_PUBLIC_URL = os.getenv("A2A_PUBLIC_URL", f"http://127.0.0.1:{A2A_PORT}")


def convert_a2ui_input(part: Part) -> types.Part | None:
    """Convert renderer actions into readable ADK user-turn text."""
    data_part = get_a2ui_datapart(part)
    if data_part is None:
        return convert_a2a_part_to_genai_part(part)

    messages = data_part.data if isinstance(data_part.data, list) else [data_part.data]
    for message in messages:
        if not isinstance(message, dict):
            continue
        action: Any = message.get("userAction") or message.get("action")
        if action:
            return types.Part.from_text(
                text="A2UI userAction: "
                + json.dumps(action, ensure_ascii=False, separators=(",", ":"))
            )
        if "error" in message:
            return types.Part.from_text(
                text="A2UI renderer error: "
                + json.dumps(message["error"], ensure_ascii=False)
            )

    return types.Part.from_text(text="The user interacted with the A2UI surface.")


class A2uiA2aEventConverter:
    """Convert ADK output to A2A parts marked for the A2UI renderer."""

    _part_converter = A2uiPartConverter(catalog)

    @classmethod
    def _convert_part(cls, part):
        """Keep A2UI as protocol DataParts on the A2A transport."""
        from a2ui.a2a.parts import create_a2ui_part

        messages = unwrap_adk_web_part(part)
        if messages:
            return [create_a2ui_part(message, version="0.8") for message in messages]
        return cls._part_converter.convert(part)

    def __call__(
        self,
        event,
        invocation_context,
        task_id=None,
        context_id=None,
        part_converter_func=convert_a2a_part_to_genai_part,
    ):
        return convert_event_to_a2a_events(
            event,
            invocation_context,
            task_id,
            context_id,
            self._convert_part,
        )


agent_card = AgentCard(
    name="A2UI Greeting Agent",
    description="An A2A agent that returns interactive A2UI surfaces and handles their actions.",
    url=A2A_PUBLIC_URL,
    version="1.0.0",
    default_input_modes=["text/plain", "application/json+a2ui"],
    default_output_modes=["text/plain", "application/json+a2ui"],
    capabilities=AgentCapabilities(
        streaming=True,
        extensions=[
            get_a2ui_agent_extension(
                version="0.8",
                supported_catalog_ids=[catalog.catalog_id],
            )
        ],
    ),
    skills=[
        AgentSkill(
            id="interactive_a2ui",
            name="Interactive A2UI conversation",
            description="Creates interactive cards and handles their form submissions and confirmations.",
            tags=["A2UI", "forms", "confirmation"],
        )
    ],
)


def executor_factory(runner):
    return A2aAgentExecutor(
        runner=runner,
        config=A2aAgentExecutorConfig(
            a2a_part_converter=convert_a2ui_input,
            event_converter=A2uiA2aEventConverter(),
        ),
        use_legacy=True,
    )


a2a_app = to_a2a(
    root_agent,
    host=A2A_HOST,
    port=A2A_PORT,
    agent_card=agent_card,
    agent_executor_factory=executor_factory,
)
