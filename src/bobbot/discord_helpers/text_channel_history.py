"""Contains the TextChannelHistory class for tracking the history of a text channel."""

import pprint
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import Logger
from typing import Callable

import discord
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from bobbot.utils import get_images_in, get_logger, time_elapsed_str, truncate_length

logger: Logger = get_logger(__name__)


def get_users_in_channel(channel: discord.DMChannel | discord.TextChannel) -> list[discord.User]:
    """Get a list of all users in a Discord channel."""
    if isinstance(channel, discord.DMChannel):
        users = channel.recipients + [channel.me]
    else:
        users = channel.members
    return users


def pings_to_usernames(content: str, channel: discord.TextChannel) -> str:
    """Replace raw ID mentions with username mentions in the given content."""
    user_mention_pattern = re.compile(r"<@!?(\d+)>")
    # Find all matches of user mentions in the content
    matches = user_mention_pattern.findall(content)
    all_users: list[discord.User] = get_users_in_channel(channel)
    for user_id in matches:
        # Check if the user is in the channel
        if (user := discord.utils.get(all_users, id=int(user_id))) is not None:
            # Replace the mention with the member's display name
            content = re.sub(f"<@!?{user_id}>", f"@{user.display_name}", content)
    return content


def get_full_content(message: discord.Message) -> str:
    """Get the full content of a message, including attachment URLs and sticker names."""
    # Replace user mentions with display names
    content: str = pings_to_usernames(message.content, message.channel)
    # Add stickers and attachments
    stickers: str = ", ".join([sticker.name for sticker in message.stickers])
    if stickers:
        content = f"{content} {stickers}"
    attachments: str = ", ".join([f"{attachment.url}" for attachment in message.attachments])
    if attachments:
        content = f"{content} {attachments}"
    # Check for embed
    if message.embeds and not content:
        pass
    return content


@dataclass
class ParsedMessage:
    """Represents a parsed Discord message."""

    message: discord.Message
    """The raw message."""
    is_deleted: bool = False
    """Whether the message was deleted."""

    @property
    def id(self) -> int:
        """The message ID."""
        return self.message.id

    @property
    def is_edited(self) -> bool:
        """Whether the message was edited."""
        return self.message.edited_at is not None

    @property
    def author(self) -> str:
        """As a string."""
        return self.message.author.display_name

    @property
    def content(self) -> str:
        """Text of the message."""
        return self.message.content

    @property
    def full_content(self) -> str:
        """Includes content, attachment URLs, and stickers."""
        return get_full_content(self.message)

    @property
    def reactions(self) -> str:
        """As a string."""
        return ", ".join([f"{r.count} {r.emoji}" for r in self.message.reactions])

    @property
    def timestamp(self) -> str:
        """Relative to now, as a string."""
        return time_elapsed_str(self.message.created_at)

    @property
    def context(self) -> str:
        """Whether the message is edited/deleted, plus if it's a reply/command response."""
        context = "Deleted" if self.is_deleted else "Edited" if self.is_edited else ""
        replying = ""
        if self.message.reference and isinstance(self.message.reference.resolved, discord.Message):
            # Replying to a message
            old_msg: discord.Message = self.message.reference.resolved
            replying = f"replying to {old_msg.author.display_name}"
        elif self.message.interaction_metadata:
            # Slash command response
            replying = "triggered by a command"
        context = f"{context}, {replying}" if context and replying else replying if replying else context
        return context

    def __init__(self, message: discord.Message, is_deleted: bool = False):
        """Create a message entry.

        Args:
            message: The message to parse.
            is_deleted: Whether the message was deleted.
        """
        self.message = message
        self.is_deleted = is_deleted

    def as_string(
        self,
        with_author: bool = True,
        with_context: bool = True,
        with_reactions: bool = True,
        with_timestamp: bool = False,
    ) -> str:
        """Format the message as a string.

        Args:
            with_author: Whether to include the author.
            with_context: Whether to include context info.
            with_reactions: Whether to include reactions.
            with_timestamp: Whether to include a timestamp.

        Returns:
            The formatted message.
        """
        result = ""
        if with_timestamp:
            result += f"[{self.timestamp}] "
        if with_author:
            if with_context and self.context:
                result += f"{self.author} ({self.context}): "
            else:
                result += f"{self.author}: "
        elif with_context and self.context:
            result += f"({self.context}) "
        result += self.full_content
        if with_reactions and self.reactions:
            result += f" | Reactions: {self.reactions}"
        return result

    def __str__(self) -> str:
        """Format the message as a full string, containing all info."""
        return self.as_string(with_timestamp=True)


class TextChannelHistory:
    """Tracks the history of a text channel, providing concise representations of messages and other events."""

    MAX_CONTENT_LENS: list[int] = [4096] * 2 + [256] * 8 + [64] * 10
    # MAX_CONTENT_LENS: list[int] = [128] * 2 + [64] * 2
    """The maximum lengths for message content, starting with the most recent."""
    MAX_MSGS: int = len(MAX_CONTENT_LENS)
    """The maximum number of messages to track."""

    channel: discord.TextChannel
    """The channel being tracked."""
    is_typing: dict[discord.User, datetime]
    """Users currently typing in the channel."""
    history: list[ParsedMessage]
    """Recent messages in the channel."""
    message_count: int
    """Counter for the total number of messages sent in the channel."""

    def __init__(self, channel: discord.TextChannel):
        """Create a tracker for the specified channel.

        Args:
            channel: The channel to track.
        """
        self.channel = channel
        self.is_typing = {}
        self.history = []
        self.message_count = 0

    def on_typing(self, user: discord.User, when: datetime) -> None:
        """Handle a typing event."""
        self.is_typing[user] = when

    def clear_users_typing(self) -> None:
        """Clear all currently typing users."""
        self.is_typing = {}

    def get_users_typing(self) -> list[discord.User]:
        """Returns a list of users currently typing."""
        # Update typing status, removing entries that are >= 10 seconds old
        now: datetime = datetime.now(timezone.utc)
        self.is_typing = {user: when for user, when in self.is_typing.items() if (now - when).total_seconds() < 10}
        return list(self.is_typing.keys())

    async def aupdate(self) -> None:
        """Update the history with the latest messages and events.

        This method should be called before querying the history after every idle period.
        """
        history: list[ParsedMessage] = []
        old_history: list[ParsedMessage] = self.history
        old_history_index: int = len(old_history) - 1
        async for prev_msg in self.channel.history(limit=TextChannelHistory.MAX_MSGS):  # From most to least recent
            # Get allowed content length
            if len(history) >= TextChannelHistory.MAX_MSGS:
                break
            # Check for messages that are already in history
            is_old: bool = False
            while old_history_index >= 0 and old_history[old_history_index].message.created_at >= prev_msg.created_at:
                old_entry: ParsedMessage = old_history[old_history_index]
                old_history_index -= 1
                if prev_msg.id == old_entry.message.id:
                    is_old = True
                    history.append(ParsedMessage(prev_msg, is_deleted=old_entry.is_deleted))
                else:
                    # Message was deleted
                    history.append(ParsedMessage(old_entry.message, is_deleted=True))
            if not is_old:
                self.message_count += 1
                if prev_msg.content.startswith(("! reset", "! mode")):
                    break  # Stop tracking history at the first command
                elif prev_msg.content.startswith("!"):
                    continue  # Skip other commands
                history.append(ParsedMessage(prev_msg))
        # Truncate history and reverse it
        history = history[: TextChannelHistory.MAX_MSGS][::-1]
        self.history = history
        logger.info("Updated text channel history.")

    def history_to_strings(self, transform: Callable[[ParsedMessage], str], limit: int = MAX_MSGS) -> list[str]:
        """Get a list of truncated strings representing the history, up to the last limit messages.

        Messages are truncated based on how recent they are, with older messages being truncated more.

        Args:
            transform: A function to convert a ParsedMessage to a string.
            limit: The maximum number of messages to include.

        Returns:
            A list of strings representing the history.
        """
        history_strs: list[str] = []
        for i, entry in enumerate(reversed(self.history[-limit:])):
            curr_str = truncate_length(transform(entry), TextChannelHistory.MAX_CONTENT_LENS[i])
            history_strs.append(curr_str)
        return history_strs[::-1]

    def as_parsed_messages(self, limit: int = MAX_MSGS) -> list[ParsedMessage]:
        """Get the channel's message history, up to the last limit messages."""
        return self.history[-limit:]

    def as_string(
        self,
        limit: int = MAX_MSGS,
        with_author: bool = True,
        with_context: bool = True,
        with_reactions: bool = True,
        with_timestamp: bool = False,
    ) -> str:
        """Get a string representation of the history, up to the last limit messages.

        Args:
            limit: The maximum number of messages to include.
            with_author: Whether to include the author.
            with_context: Whether to include context info.
            with_reactions: Whether to include reactions.
            with_timestamp: Whether to include a timestamp.

        Returns:
            A string representing the history.
        """
        result = "\n".join(
            self.history_to_strings(
                lambda e: e.as_string(
                    with_author=with_author,
                    with_context=with_context,
                    with_reactions=with_reactions,
                    with_timestamp=with_timestamp,
                ),
                limit,
            )
        )
        logger.debug(f"Text channel history as string:\n{result}")
        return result

    def as_langchain_msgs(
        self, bot_user: discord.User, limit: int = MAX_MSGS, get_image: bool = True
    ) -> list[BaseMessage]:
        """Get a list of LangChain messages representing the history, up to the last limit messages.

        Args:
            bot_user: The bot user. Used to distinguish AIMessages from HumanMessages.
            limit: The maximum number of messages to include.
            get_image: Whether to include a single image URL in the most recent message (if present).

        Returns:
            A list of LangChain message objects, with only HumanMessages containing author/context info.
        """

        def transform(entry: ParsedMessage) -> str:
            """Bot messages should not contain author or context info."""
            if entry.message.author == bot_user:
                return entry.as_string(with_author=False, with_context=False, with_reactions=True, with_timestamp=False)
            else:
                return entry.as_string(with_author=True, with_context=True, with_reactions=True, with_timestamp=False)

        history_strs: list[str] = self.history_to_strings(transform, limit)
        result: list[BaseMessage] = []
        for entry, text in zip(self.history[-limit:], history_strs):
            if entry.message.author == bot_user:
                result.append(AIMessage(content=text))
            else:
                # Include image in most recent message
                if entry == self.history[-1]:
                    image_urls: list[str] = get_images_in(text)
                    if image_urls:
                        result.append(
                            HumanMessage(
                                content=[
                                    {"type": "text", "text": text},
                                    {"type": "image_url", "image_url": {"url": image_urls[-1]}},
                                ]
                            )
                        )
                        continue
                result.append(HumanMessage(content=text))
        logger.debug(f"Text channel history as langchain messages:\n{pprint.pformat(result)}")
        return result


class ManualHistory:
    """Generate message histories manually. Messages sent by bob should always start with "bob: "."""

    def __init__(self, history: list[str] = None) -> None:
        """Initialize the message history."""
        self._history = history.copy() if history else []

    def add_message(self, message: str) -> None:
        """Add a message (with any desired context) to the message history."""
        self._history.append(message)

    def limit_messages(self, limit: int) -> None:
        """Limit the number of messages in the history."""
        self._history = self._history[-limit:]

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


channel_history: dict[int, TextChannelHistory] = {}


def get_channel_history(channel: discord.TextChannel) -> TextChannelHistory:
    """Get the history for a channel, creating it if it doesn't exist."""
    if channel.id not in channel_history:
        channel_history[channel.id] = TextChannelHistory(channel)
    return channel_history[channel.id]
