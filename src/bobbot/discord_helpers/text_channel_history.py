"""Contains the TextChannelHistory class for tracking the history of a text channel."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import Logger

import discord

from ..utils import get_logger, time_elapsed_str, truncate_middle

logger: Logger = get_logger(__name__)


def get_users_in_channel(channel: discord.DMChannel | discord.TextChannel) -> list[discord.User]:
    """Get a list of users in a Discord channel."""
    if isinstance(channel, discord.DMChannel):
        users = channel.recipients + [channel.me]
    else:
        users = channel.members
    return users


@dataclass
class MessageEntry:
    """Represents a message entry in the history."""

    message: discord.Message
    """The message."""
    string: str
    """A cached string representation of the message (without a timestamp)."""
    is_edited: bool = False
    """Whether the message was edited."""
    is_deleted: bool = False
    """Whether the message was deleted."""

    def __str__(self) -> str:
        """Convert a message entry to a string representation (with a timestamp)."""
        preamble: str = time_elapsed_str(self.message.created_at)
        # preamble: str = ""
        if self.is_edited:
            preamble = f"{preamble}, edited"
            # preamble = "[Edited] "
        elif self.is_deleted:
            preamble = f"{preamble}, deleted"
            # preamble = "[Deleted] "
        return f"[{preamble}] {self.string}"
        # return f"{preamble}{self.string}"


class TextChannelHistory:
    """Tracks the history of a text channel, providing concise representations of messages and other events."""

    MAX_CONTENT_LENS: list[int] = [4096] * 2 + [256] * 8 + [64] * 10
    # MAX_CONTENT_LENS: list[int] = [128] * 2 + [64] * 2
    """The maximum lengths for message content, starting with the most recent."""
    MAX_MSGS: int = len(MAX_CONTENT_LENS)
    """The maximum number of messages to track."""
    REPLY_CONTENT_LEN: int = 64
    """The maximum length of a reply's content."""

    def __init__(self, channel: discord.TextChannel):
        """Initialize the tracker with the specified channel.

        Args:
            channel: The channel to track.
        """
        self.channel: discord.TextChannel = channel
        """The channel being tracked."""
        self.history: list[MessageEntry] = []
        """Recent messages in the channel."""
        self.is_typing: dict[discord.User, datetime] = {}
        """Users currently typing in the channel."""
        self.message_count: int = 0
        """Counter for the total number of messages sent in a channel."""

    async def amessage_to_str(self, message: discord.Message, max_len: int = 255, core_only: bool = False) -> str:
        """Convert a message to a concise string representation (without a timestamp).

        Args:
            message: The message to convert.
            max_len: The max length of the message content.
            core_only: Whether to only include the core message content (no tracing replies or reactions).

        Returns:
            A concise string representation of the message.
        """
        # Replace user mentions with display names
        content: str = message.content
        user_mention_pattern = re.compile(r"<@!?(\d+)>")
        # Find all matches of user mentions in the content
        matches = user_mention_pattern.findall(content)
        all_users: list[discord.User] = get_users_in_channel(message.channel)
        for user_id in matches:
            # Check if the user is in the channel
            if (user := discord.utils.get(all_users, id=int(user_id))) is not None:
                # Replace the mention with the member's display name
                content = re.sub(f"<@!?{user_id}>", f"@{user.display_name}", content)

        # Add stickers and attachments
        stickers: str = ", ".join([sticker.name for sticker in message.stickers])
        if stickers:
            content = f"{content} {stickers}"
        attachments: str = ", ".join([f"{attachment.url}" for attachment in message.attachments])
        if attachments:
            content = f"{content} {attachments}"
        result: str

        if not core_only:
            author: str = message.author.display_name
            # Add reply context (if any)
            replying: str = ""
            if message.reference and isinstance(message.reference.resolved, discord.Message):
                old_msg: discord.Message = message.reference.resolved
                old_content: str = await self.amessage_to_str(
                    message.reference.resolved, max_len=TextChannelHistory.REPLY_CONTENT_LEN, core_only=True
                )
                replying = f' (replying to {old_msg.author.display_name}\'s "{old_content}")'
            # Add reactions
            reactions: str = ", ".join([f"{r.count} {r.emoji}" for r in message.reactions])
            if reactions:
                reactions = f" | Reactions: {reactions}"
            result = f"{author}{replying}: {content}{reactions}"
        else:
            result = f"{content}"
        return truncate_middle(result, max_len=max_len, replace_newlines=True)

    async def aupdate(self) -> None:
        """Update the history with the latest messages and events.

        This method should be called before querying the history after every idle period.
        """
        history: list[MessageEntry] = []
        old_history: list[MessageEntry] = self.history
        old_history_index: int = len(old_history) - 1
        async for prev_msg in self.channel.history(limit=TextChannelHistory.MAX_MSGS):  # From most to least recent
            # Get allowed content length
            if len(history) >= TextChannelHistory.MAX_MSGS:
                break
            curr_len: int = TextChannelHistory.MAX_CONTENT_LENS[len(history)]
            # Check for messages that are already in history
            is_old: bool = False
            while old_history_index >= 0 and old_history[old_history_index].message.created_at >= prev_msg.created_at:
                old_entry: MessageEntry = old_history[old_history_index]
                old_history_index -= 1
                if prev_msg.id == old_entry.message.id:
                    is_old = True
                    # Was the message edited?
                    if prev_msg.edited_at != old_entry.message.edited_at:
                        edited: str = await self.amessage_to_str(prev_msg, max_len=curr_len)
                        history.append(MessageEntry(prev_msg, edited, is_edited=True))
                    else:
                        old_content: str = truncate_middle(old_entry.string, max_len=curr_len, replace_newlines=True)
                        history.append(MessageEntry(old_entry.message, old_content, is_edited=old_entry.is_edited))
                else:
                    # Message was deleted
                    history.append(MessageEntry(old_entry.message, old_entry.string, is_deleted=True))
            if not is_old:
                self.message_count += 1
                if prev_msg.content.startswith("!"):
                    break  # Stop tracking history at the first command
                history.append(MessageEntry(prev_msg, await self.amessage_to_str(prev_msg, max_len=curr_len)))
        # Truncate history and reverse it
        history = history[: TextChannelHistory.MAX_MSGS][::-1]
        self.history = history
        logger.debug("Updated text channel history.")

    def on_typing(self, user: discord.User, when: datetime) -> None:
        """Handle a typing event."""
        self.is_typing[user] = when

    def get_history_str(self, max_msgs: int = MAX_MSGS) -> str:
        """Get a string representation of the history."""
        result: str = "\n".join([str(e) for e in self.history[-max_msgs:]])
        logger.debug(f"Text channel history:\n{result}")
        return result

    def clear_users_typing(self) -> None:
        """Clear all currently typing users."""
        self.is_typing = {}

    def get_users_typing(self) -> list[discord.User]:
        """Returns a list of users currently typing."""
        # Update typing status, removing entries that are >= 10 seconds old
        now: datetime = datetime.now(timezone.utc)
        # debug = {user.display_name: (now - when).total_seconds() for user, when in self.is_typing.items()}
        # print(f"Typing: {debug}")
        self.is_typing = {user: when for user, when in self.is_typing.items() if (now - when).total_seconds() < 10}
        return list(self.is_typing.keys())
