import os
import time
import wave

import azure.cognitiveservices.speech as speechsdk
import pyaudio
from dotenv import load_dotenv

load_dotenv()

# Initialize PyAudio
p = pyaudio.PyAudio()

# Define audio stream settings (for example, 48 kHz, 16-bit mono)
stream = p.open(format=pyaudio.paInt16, channels=1, rate=48000, output=True)


speech_config = speechsdk.SpeechConfig(
    subscription=os.environ.get("SPEECH_KEY"), region=os.environ.get("SPEECH_REGION")
)
# audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
audio_config = None

# The neural multilingual voice can speak different languages based on the input text.
speech_config.speech_synthesis_voice_name = "en-US-AshleyNeural"
speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm)

synthesizer = speechsdk.SpeechSynthesizer(speech_config, audio_config)
connection = speechsdk.Connection.from_speech_synthesizer(synthesizer)
connection.open(True)

input("Press Enter to start speaking...")

start_time = time.time()

ssml_string = """
<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xml:lang="en-US">
  <voice name="en-US-AshleyNeural">
    <prosody pitch='+25%'>
      Hello. I am Neurosama. I like trains :D. abcdefgh lol BYE
    </prosody>
  </voice>
</speak>
"""

result = synthesizer.start_speaking_ssml_async(ssml_string).get()
audio_data_stream = speechsdk.AudioDataStream(result)
audio_buffer = bytes(4096)  # Adjust buffer size as necessary

# Save to file
wav_file = wave.open("output.wav", "wb")
wav_file.setnchannels(1)
wav_file.setsampwidth(p.get_sample_size(pyaudio.paInt16))
wav_file.setframerate(48000)

# Stream and play the audio as it is received
filled_size = audio_data_stream.read_data(audio_buffer)
# 0.906s without pre-connecting, 0.190s with pre-connecting, that's honestly amazing latency.
print(f"Time to stream start: {time.time() - start_time:.3f}s")
while filled_size > 0:
    stream.write(audio_buffer[:filled_size])  # Play the received audio data
    wav_file.writeframes(audio_buffer[:filled_size])  # Save the received audio data to a file
    print(f"{filled_size} bytes received.")
    filled_size = audio_data_stream.read_data(audio_buffer)  # Read next chunk

# Clean up
stream.stop_stream()
stream.close()
p.terminate()
wav_file.close()
