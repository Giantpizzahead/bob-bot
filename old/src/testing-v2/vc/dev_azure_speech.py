import os
import time

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()


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

# ssml_string = open("src/ssml.xml", "r").read()
ssml_string = """
<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xml:lang="en-US">
  <voice name="en-US-AshleyNeural">
    <prosody pitch='+25%'>
      Hello. I am Neurosama. I like trains :D. abcdefgh lol BYE
    </prosody>
  </voice>
</speak>
"""
# result = synthesizer.speak_ssml_async(ssml_string).get()

speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
result = speech_synthesizer.start_speaking_text_async(ssml_string).get()
audio_data_stream = speechsdk.AudioDataStream(result)
audio_buffer = bytes(48000)
print(f"Time to stream start: {time.time() - start_time:.3f}s")
filled_size = audio_data_stream.read_data(audio_buffer)
while filled_size > 0:
    print("{} bytes received.".format(filled_size))
    filled_size = audio_data_stream.read_data(audio_buffer)
print(f"Time to stream end: {time.time() - start_time:.3f}s")
audio_data_stream.save_to_wav_file("src/out.wav")
