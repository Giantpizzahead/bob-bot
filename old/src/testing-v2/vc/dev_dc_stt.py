import asyncio
import os
import platform
import wave

import discord
import numpy as np
import resampy
from discord.ext import voice_recv
from dotenv import load_dotenv
from scipy.signal import decimate, resample, resample_poly
from scipy.signal.windows import hamming

load_dotenv()
if platform.system() == "Darwin":  # Manual load for Mac
    discord.opus.load_opus("libopus.0.dylib")


class RealTimeResampler:
    def __init__(self, input_rate, output_rate, chunk_size):
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.chunk_size = chunk_size  # Size of the input chunks (in samples)
        self.overlap_size = chunk_size // 2
        self.prev_chunk = np.zeros(self.overlap_size, dtype=np.float32)

    def process_chunk(self, chunk):
        # Apply a window function to the chunk
        window = hamming(len(chunk))
        windowed_chunk = chunk * window

        # Resample the chunk
        resampled_chunk = resample_poly(windowed_chunk, self.output_rate, self.input_rate)

        # Combine with the previous chunk using overlap-add
        overlap_add_result = np.concatenate((self.prev_chunk, resampled_chunk[: self.overlap_size]))
        self.prev_chunk = resampled_chunk[self.overlap_size :]

        return overlap_add_result


sampler = RealTimeResampler(1, 6, 100)


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_files: dict[int, wave.Wave_write] = {}

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):
        if message.content.startswith("/vc"):

            def callback(user: discord.User, data: voice_recv.VoiceData):
                packet = data.packet
                print(packet)
                # print(data.pcm)
                print(f"Got packet from {user}")

                ext_data = packet.extension_data.get(voice_recv.ExtensionID.audio_power)
                if ext_data:
                    value = int.from_bytes(ext_data, "big")
                    power = 127 - (value & 127)
                    print(f"Power: {power}")

                # Save raw PCM data to a file
                if user.id not in self.audio_files:
                    self.audio_files[user.id] = wave.open(f"{user.id}.wav", "wb")
                    self.audio_files[user.id].setnchannels(1)  # Mono
                    self.audio_files[user.id].setsampwidth(2)  # 16-bit PCM
                    self.audio_files[user.id].setframerate(16000)  # 48kHz

                # Convert the byte data to a NumPy array
                pcm_data = np.frombuffer(data.pcm, dtype=np.int16)

                resampled_data = decimate(pcm_data, 6)

                # Resample the data from the original sample rate (96kHz) to 48kHz
                # num_samples = int(len(pcm_data) * (16000 / channel.bitrate))
                # downsampled_data = resample(pcm_data, num_samples)
                # Resample
                # # Just take every 6th sample
                # resampled_data = pcm_data[::6]
                # resampled_data = resampy.resample(pcm_data, sr_orig=channel.bitrate, sr_new=16000, filter="kaiser_fast")
                resampled_data_bytes = resampled_data.astype(np.int16).tobytes()

                # Convert back to bytes and write to the file
                self.audio_files[user.id].writeframes(resampled_data_bytes)

            channel: discord.VoiceChannel = message.author.voice.channel
            vc: voice_recv.VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.listen(voice_recv.BasicSink(callback))

    async def on_speaking(self, user, speaking):
        if speaking:
            print(f"{user} is speaking")
        else:
            print(f"{user} stopped speaking")
            # Close the audio file if user stopped speaking
            if user.id in self.audio_files:
                self.audio_files[user.id].close()
                del self.audio_files[user.id]


intents = discord.Intents.all()
client = MyClient(intents=intents)

client.run(os.getenv("DISCORD_TOKEN"))
