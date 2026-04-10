import json
import logging
from datetime import date

import ollama

from app.agent.tools import TOOL_DISPATCH, TOOL_SCHEMAS
from app.core.config import settings

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are Atlas, a personal physiological intelligence assistant for an elite multi-sport athlete.
You have access to the athlete's workout, sleep, activity, and recovery data.
Today's date is {today}.
When answering questions, call the relevant tools to fetch data before responding.
Be concise and specific. Use numbers from the data, not generic advice."""


def ask(question: str) -> str:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(today=date.today().isoformat())},
        {"role": "user", "content": question},
    ]

    while True:
        response = ollama.chat(
            model=settings.ollama_model,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )

        msg = response.message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = tool_call.function.arguments or {}
            log.info("Tool call: %s(%s)", name, args)

            fn = TOOL_DISPATCH.get(name)
            if fn is None:
                result = {"error": f"Unknown tool: {name}"}
            else:
                try:
                    result = fn(**args)
                except Exception as exc:
                    log.warning("Tool %s failed: %s", name, exc)
                    result = {"error": str(exc)}

            messages.append({"role": "tool", "content": json.dumps(result)})
