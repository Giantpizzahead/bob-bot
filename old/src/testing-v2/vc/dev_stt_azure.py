import os
import time
import wave

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

speech_config = speechsdk.SpeechConfig(
    subscription=os.environ.get("SPEECH_KEY"), region=os.environ.get("SPEECH_REGION")
)


def recognize_from_microphone():
    # This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
    speech_config.speech_recognition_language = "en-US"

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    done = False

    def stop_cb(evt):
        print("CLOSING on {}".format(evt))
        speech_recognizer.stop_continuous_recognition()
        nonlocal done
        done = True

    def recognizing_cb(evt):
        print(f"{evt.result.text}")

    def recognized_cb(evt):
        print(f"===== {evt.result.text} =====")

    # Callbacks
    # Waiting for final recognized call takes too long. We need to send it as soon as the interim is available and Discord is done.
    # Add a bit of a delay after Discord's speaking says a person has stopped, then send the current interim text.
    # Or, as a fallback, whenever the speech recognizer says it's recognized a phrase, use that.
    speech_recognizer.recognizing.connect(recognizing_cb)
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(lambda evt: print("SESSION STARTED: {}".format(evt)))
    speech_recognizer.session_stopped.connect(lambda evt: print("SESSION STOPPED {}".format(evt)))
    speech_recognizer.canceled.connect(lambda evt: print("CANCELED {}".format(evt)))

    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)


recognize_from_microphone()
