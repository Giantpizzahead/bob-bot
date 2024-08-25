import json
import os

import discord
from discord.ext import commands
from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .utils import get_logger

logger = get_logger(__name__)


def run_bot() -> None:
    # Langchain setup
    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_KEY"),
        model="gpt-4o-mini",
        temperature=1,
        max_tokens=256,
        top_p=0.8,
        frequency_penalty=0.05,
        presence_penalty=0.05,
    )

    async def get_response(message: str) -> str:
        messages = [
            SystemMessage(
                content=(
                    "You are a Discord user named Bob chatting in a private Discord server. "
                    "Bob is a rising junior majoring in CS at MIT and is a witty gamer. "
                    "There are other users too. Avoid rambling for too long, split long messages into short ones, "
                    "and don't repeat yourself. Keep messages like reddit comments - short, witty, and in all lowercase, "
                    "with abbreviations and little care for grammar."
                )
            ),
            HumanMessage(content=message),
        ]
        response = await llm.ainvoke(messages)
        return response.content

    # Discord handling

    intents = discord.Intents.default()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    intents.voice_states = True
    intents.members = True

    client = commands.Bot(command_prefix="!", intents=intents)

    @client.event
    async def on_ready() -> None:
        logger.info("Bob is now online!")

    active_channel = None

    async def send_discord_message(message_str: str) -> None:
        global active_channel
        if not active_channel:
            raise ValueError("No active channel!")
        await active_channel.send(message_str[-1980:])

    CHANNELS = json.loads(os.getenv("DISCORD_CHANNELS", "[]"))

    @client.event
    async def on_message(message):
        logger.info(f"Received message: {message.content}, {message.channel.id}, {CHANNELS}")
        global active_channel
        if message.author.bot:
            return

        if not (str(message.channel.id) in CHANNELS or client.user.mentioned_in(message)):
            return

        active_channel = message.channel

        try:
            response = await get_response(message.content)
            await send_discord_message(response)
        except Exception as e:
            print(e)
            await send_discord_message(str(e))

    client.run(os.getenv("DISCORD_TOKEN"))
