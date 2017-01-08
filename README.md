# Simple Python AVS API Client (Alexa Voice Service)

### Uses the latest AVS API: v20160207
### In theory supports both Python 2.7 and 3+

https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/content/avs-api-overview

Very much a work in progress, but the basic structure works.

Note: this is not meant to act as a "device", this is a simple interface to the AVS API which requires you to send/respond to the events and directives that AVS uses.

## Install
`pip install simpleavs`

## Example usage

```python
import simpleavs

def handle_speak(speak_directive):
    """ called when a speak directive is received from AVS """
    play_mp3_data(speak_directive.audio_data)

# AvsClient requires a dict with client_id, client_secret, refresh_token
avs = simpleavs.AvsClient(config)

avs.speech_synthesizer.speak_event += handle_speak

avs.connect()

avs.speech_recognizer.recognize(audio_data=wav_request_data, profile='NEAR_FIELD')

# sleep / poll for quit

avs.disconnect()
```

### Roadmap

* tests
* more examples
* tests
* documentation
* and probably could do with some tests


Originally ported from: https://github.com/nicholasjconn/python-alexa-voice-service
