"""Generates mock message histories for testing."""

from langchain_core.messages import AIMessage, HumanMessage


class MockHistory:
    """Generates mock message histories for testing. Messages sent by bob should always start with "bob: "."""

    def __init__(self, history: list[str] = None) -> None:
        """Initialize the message history."""
        self._history = history.copy() or []

    def add_message(self, message: str) -> None:
        """Add a message (with any desired context) to the message history."""
        self._history.append(message)

    def as_string(self) -> str:
        """Return the full message history."""
        return "\n".join(self._history)

    def as_langchain_msgs(self) -> list[str]:
        """Return the message history as Langchain messages."""
        msgs = []
        for msg in self._history:
            if msg.startswith("bob: "):
                msgs.append(AIMessage(msg[5:]))
            else:
                msgs.append(HumanMessage(msg))
        return msgs
