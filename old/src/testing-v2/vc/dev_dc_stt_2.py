import asyncio
import os
import platform

import azure.cognitiveservices.speech as speechsdk
import discord
import numpy as np
import resampy
from discord.ext import voice_recv
from dotenv import load_dotenv

load_dotenv()
if platform.system() == "Darwin":  # Manual load for Mac
    discord.opus.load_opus("libopus.0.dylib")


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_streams = {}

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):
        if message.content.startswith("/vc"):
            channel: discord.VoiceChannel = message.author.voice.channel
            vc: voice_recv.VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.listen(voice_recv.BasicSink(self.audio_callback))

    def audio_callback(self, user: discord.User, data: voice_recv.VoiceData):
        # packet = data.packet
        # pcm_data = np.frombuffer(packet.data, dtype=np.int16)
        pcm_data = np.frombuffer(data.pcm, dtype=np.int16)

        # Resample
        resampled_data = pcm_data[::6]
        # resampled_data = resampy.resample(pcm_data, sr_orig=96000, sr_new=16000)  # Can use filter="kaiser_fast"
        resampled_data_bytes = resampled_data.astype(np.int16).tobytes()

        if user.id not in self.audio_streams:
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv("SPEECH_KEY"), region=os.getenv("SPEECH_REGION")
            )
            stream = speechsdk.audio.PushAudioInputStream()
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            speech_recognizer.recognizing.connect(lambda evt: print("RECOGNIZING: {}".format(evt)))
            speech_recognizer.recognized.connect(lambda evt: print("RECOGNIZED: {}".format(evt)))
            speech_recognizer.session_started.connect(lambda evt: print("SESSION STARTED: {}".format(evt)))
            speech_recognizer.session_stopped.connect(lambda evt: print("SESSION STOPPED {}".format(evt)))
            speech_recognizer.canceled.connect(lambda evt: print("CANCELED {}".format(evt)))
            speech_recognizer.start_continuous_recognition_async()
            self.audio_streams[user.id] = {"recognizer": speech_recognizer, "stream": stream}
        # Push the resampled audio data to the Azure stream
        self.audio_streams[user.id]["stream"].write(resampled_data_bytes)
        print(f"Audio data length: {len(resampled_data_bytes)}")
        # The speech site expects constant input (mostly) in order to output recognized
        # Right now, since we only send when speaking, it essentially cuts out periods of silence

    async def on_speaking(self, user, speaking):
        print(f"{user} is speaking: {speaking}")
        if not speaking and user.id in self.audio_streams:
            print("Closing stream")
            self.audio_streams[user.id]["stream"].close()
            await self.audio_streams[user.id]["recognizer"].stop_continuous_recognition_async()
            del self.audio_streams[user.id]


intents = discord.Intents.all()
client = MyClient(intents=intents)

client.run(os.getenv("DISCORD_TOKEN"))
