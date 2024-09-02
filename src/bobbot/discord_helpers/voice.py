"""Contains voice channel related functionality."""

import asyncio
import os
import platform
from pathlib import Path
from xml.sax.saxutils import escape

import azure.cognitiveservices.speech as speechsdk
import discord
import numpy as np
from discord.ext import commands, voice_recv
from scipy.signal import decimate, resample

from bobbot.activities import Activity, get_activity
from bobbot.agents import get_vc_response
from bobbot.discord_helpers import ManualHistory
from bobbot.discord_helpers.main_bot import bot
from bobbot.utils import get_logger, on_heroku, truncate_length

if platform.system() == "Darwin":  # Manual load for Mac
    discord.opus.load_opus("libopus.0.dylib")

SPEECH_LOG_PATH = Path("local/speechsdk.log")
Path(SPEECH_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)

logger = get_logger(__name__)

# Setup Azure STT
speech_config = speechsdk.SpeechConfig(
    subscription=os.getenv("SPEECH_KEY"), region=os.getenv("SPEECH_REGION"), speech_recognition_language="en-US"
)
speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
speech_config.set_property(speechsdk.PropertyId.Speech_LogFilename, str(SPEECH_LOG_PATH))

# Setup Azure TTS
speech_config.speech_synthesis_voice_name = "en-US-AshleyNeural"
speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm)
synthesizer = speechsdk.SpeechSynthesizer(speech_config, None)
connection = None


class AzureSTTConnection:
    """Represents an active STT connection to Azure."""

    user: discord.Member
    stream: speechsdk.audio.PushAudioInputStream
    recognizer: speechsdk.SpeechRecognizer
    text: str = ""
    """The currently recognized text."""
    is_final: bool = False
    """Whether the recognized text is final."""

    def __init__(self, user: discord.Member):
        """Initialize a connection for the given user."""
        self.user = user
        self.stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=self.stream)
        self.recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        self.recognizer.recognizing.connect(self._on_recognizing)
        self.recognizer.recognized.connect(self._on_recognized)
        self.recognizer.session_started.connect(self._on_session_started)
        self.recognizer.session_stopped.connect(self._on_session_stopped)
        self.recognizer.canceled.connect(self._on_canceled)
        self.recognizer.start_continuous_recognition_async()

    def close(self):
        """Close the connection."""
        self.recognizer.stop_continuous_recognition_async()

    def _on_recognizing(self, evt):
        """Called when interim results are received."""
        self.text = evt.result.text
        logger.info(f"Interim for {self.user.display_name}: {evt.result.text}")

    def _on_recognized(self, evt):
        """Called when final results are received."""
        self.text = evt.result.text.strip()
        self.is_final = True
        if not self.text:
            return
        logger.info(f"Final result for {self.user.display_name}: {evt.result.text}")
        new_messages.put_nowait((self.user, self.text))
        logger.info("Added to queue.")
        self.stream.close()

    def _on_session_started(self, evt):
        """Called when the session starts."""
        # logger.info(f"STT session started for {self.user.display_name}")
        pass

    def _on_session_stopped(self, evt):
        """Called when the session stops."""
        # logger.info(f"STT session stopped for {self.user.display_name}")
        pass

    def _on_canceled(self, evt):
        """Called when the session is canceled."""
        logger.warning(f"STT session canceled for {self.user.display_name}")


stt_conns: dict[int, AzureSTTConnection] = {}
vc_histories: dict[int, ManualHistory] = {}
new_messages: asyncio.Queue = asyncio.Queue()


def process_voice_packet(user: discord.Member, data: voice_recv.VoiceData) -> None:
    """Process a voice packet from another user (?)."""
    TARGET_BITRATE = 16000
    try:
        packet: voice_recv.rtp.AudioPacket = data.packet
        channel: discord.VoiceChannel = user.voice.channel

        # Check if audio is loud enough to initiate STT
        power_level = packet.extension_data.get(voice_recv.ExtensionID.audio_power)
        if power_level:
            power_level = int.from_bytes(power_level, "big")
            power_level = 127 - (power_level & 127)
            if power_level < 80 and user.id not in stt_conns:
                return  # Assume frivolous noise

        if packet.is_silence():
            # Stop the recognizer (if present) and close the stream
            if user.id in stt_conns:
                stt_conns[user.id].close()
                del stt_conns[user.id]
            return

        stt_conn: AzureSTTConnection
        if user.id not in stt_conns:
            stt_conn = stt_conns[user.id] = AzureSTTConnection(user)
        else:
            stt_conn = stt_conns[user.id]

        # Get PCM data and resample to 16 kHz
        raw_pcm = np.frombuffer(data.pcm, dtype=np.int16)
        orig_bitrate = channel.bitrate
        # Check if the bitrate is a multiple of the target bitrate
        if orig_bitrate % TARGET_BITRATE == 0:
            resampled_pcm = decimate(raw_pcm, orig_bitrate // TARGET_BITRATE)
        else:
            # Fallback if not a multiple
            num_samples = int(len(raw_pcm) * (TARGET_BITRATE / channel.bitrate))
            resampled_pcm = resample(raw_pcm, num_samples)

        # Convert back to bytes and write to stream
        resampled_bytes = resampled_pcm.astype(np.int16).tobytes()
        stt_conn.stream.write(resampled_bytes)
    except Exception as e:
        logger.exception(f"Error processing voice packet from {user.display_name}: {e}")


def prepare_tts() -> None:
    """Prepare the TTS connection."""
    global connection
    if connection is None:
        connection = speechsdk.Connection.from_speech_synthesizer(synthesizer)
        connection.open(True)
        logger.info("TTS connection opened.")


class AzureTTSStream(discord.AudioSource):
    """Represents an audio stream for Azure TTS. This is a very scrappy implementation, but it works."""

    def __init__(self, audio_data_stream):
        """Initialize the stream with the given audio data stream."""
        self.audio_data_stream = audio_data_stream
        self.encoder = discord.opus.Encoder()
        self.frame_size = 960  # 20ms at 48kHz

    def read(self):
        """Read the next frame of audio data."""
        # 20ms of 48kHz 16-bit mono PCM is 960 samples (1920 bytes)
        # We will need to double this for stereo (3840 bytes)
        MONO_BYTES = 1920
        audio_buffer = bytes(MONO_BYTES)
        filled_size = self.audio_data_stream.read_data(audio_buffer)
        if filled_size > 0:
            pcm_mono_data = audio_buffer[:filled_size]
            # If not full, pad with silence to avoid sudden cutoff
            if filled_size < MONO_BYTES:
                pcm_mono_data += b"\x00" * (MONO_BYTES - filled_size)
            # Convert mono to stereo by duplicating each sample
            pcm_stereo_data = b"".join([pcm_mono_data[i : i + 2] * 2 for i in range(0, len(pcm_mono_data), 2)])
            # Encode the stereo PCM data to Opus using discord.opus.Encoder
            opus_data = self.encoder.encode(pcm_stereo_data, self.frame_size)
            return opus_data
        return b""

    def is_opus(self):
        """Return whether the audio source is in Opus format."""
        return True


def xmlescape(data):
    """Escape XML entities in the given data."""
    return escape(data, entities={"'": "&apos;", '"': "&quot;"})


async def speak_tts(vc: voice_recv.VoiceRecvClient, text: str) -> None:
    """Speak the given text using TTS in a familiar voice."""
    if connection is None:
        logger.warning("TTS connection was not pre-opened.")
        prepare_tts()
    ssml_string = f"""
<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="en-US-AshleyNeural">
        <prosody pitch='+25%' rate='+5%'>
            {xmlescape(text)}
        </prosody>
    </voice>
</speak>
    """

    result = synthesizer.start_speaking_ssml_async(ssml_string).get()
    audio_data_stream = speechsdk.AudioDataStream(result)

    # Stream the audio to the voice channel
    audio_source = AzureTTSStream(audio_data_stream)
    logger.info(f"Speaking in VC - {text}")
    vc.play(audio_source)

    # Wait until the audio stream ends
    while vc.is_playing():
        await asyncio.sleep(0.05)


@bot.hybrid_command(name="tts")
async def discord_tts(ctx: commands.Context, *, text: str) -> None:
    """Speak the given text in a familiar voice."""
    if ctx.author.voice is None:
        await ctx.send("! but ur not in vc?")
        return
    elif len(text) > 1024:
        await ctx.send("! text too long")
        return
    # Connect/disconnect if we were previously in VC
    channel = ctx.author.voice.channel
    was_in_vc = any(vc.channel == channel for vc in bot.voice_clients)
    if was_in_vc:
        vc = ctx.voice_client
    else:
        vc = await channel.connect()
    await ctx.send("! ok")
    await speak_tts(vc, text)

    if not was_in_vc:
        await asyncio.sleep(1)  # Give time for the audio to finish
        close_tts()
        await vc.disconnect()


def close_tts() -> None:
    """Close the TTS connection."""
    global connection
    if connection is not None:
        connection.close()
        connection = None
        logger.info("TTS connection closed.")


@bot.hybrid_group(name="vc", fallback="join")
async def join_vc(ctx: commands.Context) -> None:
    """Tell Bob to join your voice channel."""
    if ctx.author.voice is None:
        await ctx.send("! but ur not in vc?")
        return
    elif ctx.voice_client is not None:
        await ctx.send("! im already in vc?")
        return
    elif on_heroku() and get_activity() == Activity.CHESS:  # Too much memory
        await ctx.send("! (heroku) can't join vc while playing chess")
        return
    channel: discord.VoiceChannel = ctx.author.voice.channel
    vc_histories[channel.id] = ManualHistory()
    vc: voice_recv.VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)
    vc.listen(voice_recv.BasicSink(process_voice_packet))
    await ctx.send(
        "! hopping on :D\n\n**Tip: VC works best if you keep it turn-based. Speak without pausing, and let Bob finish.**\nBob responds to the first person that finishes talking after Bob does. If he stops answering, make him leave and rejoin."  # noqa: E501
    )

    # Handle messages and leave if VC is empty
    while vc.is_connected() and len(vc.channel.members) > 1:
        try:
            user, message = new_messages.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)  # Manual polling for speed
            continue
        await process_vc_message(vc, user, message)
        # Clear the queue
        while not new_messages.empty():
            new_messages.get_nowait()
    if vc.is_connected():
        await vc.disconnect()


@join_vc.command(name="leave")
async def leave_vc(ctx: commands.Context) -> None:
    """Tell Bob to leave your voice channel."""
    if ctx.voice_client is None:
        await ctx.send("! im not in vc?")
        return
    # Remove VC history (if it exists)
    channel_id = ctx.voice_client.channel.id
    if channel_id in vc_histories:
        del vc_histories[channel_id]
    await ctx.voice_client.disconnect()
    await ctx.send("! ok bye D:")


@join_vc.command(name="log")
async def log_vc(ctx: commands.Context) -> None:
    """Show the current VC conversation history."""
    if ctx.voice_client is None:
        await ctx.send("! im not in vc?")
        return
    channel_id = ctx.voice_client.channel.id
    # user.guild.voice_client works too
    if channel_id not in vc_histories:
        await ctx.send("! no log for this vc")
        return
    history = vc_histories[channel_id]
    await ctx.send(f"!```VC conversation history:\n{history.as_string()}```")


async def process_vc_message(vc: voice_recv.VoiceRecvClient, user: discord.Member, message: str) -> None:
    """Process a complete audio message from a user in VC."""
    if user.voice is None:
        logger.warning(f"User {user.display_name} is not in a voice channel.")
        return
    history: ManualHistory = vc_histories[user.voice.channel.id]
    history.add_message(f"{user.display_name}: {message}")
    history.limit_messages(10)
    logger.info(f"Responding in VC - {user.display_name}: {message}")
    prepare_tts()
    response = await get_vc_response(history.as_langchain_msgs())
    history.add_message(f"bob: {response}")
    await speak_tts(vc, truncate_length(response, 256))
    close_tts()
