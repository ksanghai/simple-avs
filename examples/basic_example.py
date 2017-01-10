""" basic example demonstrating client usage """

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import os
import sys
import io
import time
import yaml

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import simpleavs  # pylint: disable=wrong-import-position

_EXAMPLES_DIR = os.path.dirname(__file__)
_CONFIG_PATH = os.path.join(_EXAMPLES_DIR, 'client_config.yml')
_REQUEST_PATH = os.path.join(_EXAMPLES_DIR, 'request.wav')

#  import logging
#  logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def main():
    """ basic example demonstrating client usage """
    avs = None

    def handle_speak(speak_directive):
        """ called when a speak directive is received from AVS """
        print('Received a Speak directive from Alexa')
        print('Notifying AVS that we have started speaking')
        avs.speech_synthesizer.speech_started(speak_directive.token)

        # save the mp3 audio that AVS sent us as part of the Speak directive
        print('(play speak.mp3 to hear how Alexa responded)')
        with io.open('speak.mp3', 'wb') as speak_file:
            speak_file.write(speak_directive.audio_data)

        print('Notifying AVS that we have finished speaking')
        avs.speech_synthesizer.speech_finished(speak_directive.token)

    with io.open(_CONFIG_PATH, 'r') as cfile:
        config = yaml.load(cfile)

    # AvsClient requires a dict with client_id, client_secret, refresh_token
    avs = simpleavs.AvsClient(config)

    # handle the Speak directive event when sent from AVS
    avs.speech_synthesizer.speak_event += handle_speak

    print('Connecting to AVS')
    avs.connect()

    # send AVS a wav request (LE, 16bit, 16000 sample rate, mono)
    with io.open(_REQUEST_PATH, 'rb') as request_file:
        request_data = request_file.read()

    print('Sending Alexa a voice request')
    avs.speech_recognizer.recognize(audio_data=request_data,
                                    profile='NEAR_FIELD')

    # once AVS has processed the request we should receive a Speak event

    time.sleep(5)
    print('Disconnecting from AVS')
    avs.disconnect()


if __name__ == '__main__':
    main()
