import asyncio
import os
import platform

import discord
from discord.ext import commands, voice_recv
from dotenv import load_dotenv

load_dotenv()
if platform.system() == "Darwin":  # Manual load for Mac
    print(discord.opus.load_opus("libopus.0.dylib"))


class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):
        if message.content.startswith("/vc"):

            def callback(user, data: voice_recv.VoiceData):
                print(f"Got packet from {user}")

                ## voice power level, how loud the user is speaking
                ext_data = data.packet.extension_data.get(voice_recv.ExtensionID.audio_power)
                value = int.from_bytes(ext_data, "big")
                power = 127 - (value & 127)
                print("#" * int(power * (79 / 128)))

            channel: discord.VoiceChannel = message.author.voice.channel
            vc: voice_recv.VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.play(discord.FFmpegPCMAudio("local/song.mp3"))
            # vc.listen(voice_recv.BasicSink(callback))

    async def on_speaking(self, user, speaking):
        if speaking:
            print(f"{user} is speaking")
        else:
            print(f"{user} stopped speaking")


intents = discord.Intents.all()
client = MyClient(intents=intents)

client.run(os.getenv("DISCORD_TOKEN"))
