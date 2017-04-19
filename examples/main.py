#! /usr/bin/env python

""" AVS v20160207 client implementation

Usage:
  main.py [options]
  main.py noavs [options]
  main.py noavs [options] [--play=<file>]

Options:
  -h --help                     Shows this help message.
  -s, --saverecordings          Save all the querys
  --record-multiple             Keep recording until user stops the client using Ctrl-C
  -d, --debug                   Turn debug messages on
"""

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import sys
import io
import yaml
import os
import dateutil.parser
from datetime import datetime
import pytz

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import simpleavs  # pylint: disable=wrong-import-position

_EXAMPLES_DIR = os.path.dirname(__file__)
_CONFIG_PATH = os.path.join(_EXAMPLES_DIR, 'client_config.yml')
_REQUEST_PATH = os.path.join(_EXAMPLES_DIR, 'request.wav')


from docopt import docopt
import random
import time
import spidev
import RPi.GPIO as GPIO
import alsaaudio
import wave
import random
import requests
import json
import re
from memcache import Client
import vlc
import threading
from threading import Event, Thread
import cgi 
import email
import time
from shutil import copyfile
from vlc import EventType
from Queue import Queue
import numpy as np
import tunein as tunein

from future.builtins import bytes

#Settings
button = 17  		# GPIO Pin with button connected
#Setup
servers = ["127.0.0.1:11211"]
mc = Client(servers, debug=1)
path = os.path.realpath(__file__).rstrip(os.path.basename(__file__))

#Debug
debug = 0

class bcolors:
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

def internet_on():
	print("Checking Internet Connection...")
	try:
		r =requests.get('https://api.amazon.com/auth/o2/token')
		print("Connection {}OK{}".format(bcolors.OKGREEN, bcolors.ENDC))
		return True
	except:
		print("Connection {}Failed{}".format(bcolors.WARNING, bcolors.ENDC))
		return False


def mrl_fix(url):
	if ('#' in url) and url.startswith('file://'):
		new_url = url.replace('#', '.hashMark.')
		os.rename(url.replace('file://', ''), new_url.replace('file://', ''))
		url = new_url

	return url

class Player(object):

	def __init__(self, dialog_callback=None, content_callback=None, alert_callback=None, avs=None,  avs_callback=None, default_vol=80, max_vol=100, min_vol=30):
		self.p_content = ""
		self.p_dialog = ""
		self.p_alert = ""

		self.content_playing = False
		self.dialog_playing = False

		self.dialog_callback = dialog_callback
		self.content_callback = content_callback
		self.alert_callback = alert_callback

		self.avs =avs
		self.avs_callback = avs_callback

		self.tunein_parser = tunein.TuneIn(5000)

		self._curr_volume = default_vol
		self._max_vol = max_vol
		self._min_vol = min_vol

	def set_volume(self, volume, adjust=False):
		if adjust:
			volume = self._curr_volume + volume

		if (volume > self._max_vol):
			volume = self._max_vol
		elif (volume < self._min_vol):
			volume = self._min_vol

		self._curr_volume = volume

		if self.p_content != "":
			self.p_content.audio_set_volume(volume)
		if self.p_dialog != "":
			self.p_dialog.audio_set_volume(volume)
		if self.p_alert != "":
			self.p_alert.audio_set_volume(volume)

		if debug: print("new volume = {}".format(volume))

	def get_volume(self, volume):
		self._curr_volume = volume

	def set_background(self, channel, level=0.5):
		volume = int(self._curr_volume*level)
		if channel == 'content':
			if self.p_content != "":
				self.p_content.audio_set_volume(volume)
		if channel == 'dialog':
			if self.p_dialog != "":
				self.p_dialog.audio_set_volume(volume)
		if channel == 'alert':
			if self.p_alert != "":
				self.p_alert.audio_set_volume(volume)

	def set_foreground(self, channel, level=1):
		volume = int(self._curr_volume*level)

		if volume > self._max_vol:
			volume = self._max_vol

		if channel == 'content':
			if self.p_content != "":
				self.p_content.audio_set_volume(volume)
		if channel == 'dialog':
			if self.p_dialog != "":
				self.p_dialog.audio_set_volume(volume)
		if channel == 'alert':
			if self.p_alert != "":
				self.p_alert.audio_set_volume(volume)

	def play(self, content, channel='dialog', directive=None, offset=0, overRideVolume=0):

		# i = vlc.Instance('--aout=alsa', '--file-logging', '--logfile=vlc-log.txt')
		if channel == 'dialog':
			if self.dialog_playing:
				self.p_dialog.stop()
			i = vlc.Instance('--aout=alsa')
			m = i.media_new(content)
			self.p_dialog= i.media_player_new()
			self.p_dialog.set_media(m)
			# mm = player.p_dialogevent_manager()
			# mm.event_attach(vlc.EventType.MediaPlayerEndReached, state_callback_dialog, speak_directive)
			mm = m.event_manager()
			mm.event_attach(vlc.EventType.MediaStateChanged, self.dialog_callback, self.avs, self, self.avs_callback, directive)

			self.dialog_playing = True
			self.set_foreground('dialog')

			if debug: print(self.content_playing)
			self.p_dialog.play()

		if channel == 'content':
			if self.p_content != "":
				self.p_content.stop()
			if (content.find('radiotime.com') != -1):
				content = self.tunein_playlist(content)
				content = mrl_fix(content)
			if debug: print("{}Play_Audio Request for:{} {}".format(bcolors.OKBLUE, bcolors.ENDC, content))
			i = vlc.Instance('--aout=alsa', '--file-logging', '--logfile=vlc-log-audio.txt')
			m = i.media_new(content)
			self.p_content = i.media_player_new()
			self.p_content.set_media(m)
			mm = m.event_manager()
			mm.event_attach(vlc.EventType.MediaStateChanged, self.content_callback, self.avs, self, self.avs_callback, directive)
			self.content_playing = True
			self.p_content.play()

	def stop(self, channel=None):
		if channel == 'dialog':
			if self.p_dialog!= "": self.p_dialog.stop() 
		if channel == 'content':
			if self.p_content != "": self.p_content.stop()
		if channel == 'alert':
			if self.p_alert != "": self.p_alert.stop()

	def tunein_playlist(url):
		req = requests.get(url)
		lines = req.content.decode().split('\n')

		nurl = self.tunein_parser.parse_stream_url(lines[0])
		if nurl:
			return nurl[0]

		return ""


class Audio(object):
    """
	A class implementing buffered audio I/O.
    """

    def __init__(self, rate=16000, period=320):
        self.__rate = rate
        self.__period = period
        # self.__read_queue = Queue(maxsize=32000)
        self.__read_queue = Queue()
	self.__read_thread = ''

    """
    Reads audio from an ALSA audio device into the read queue.
    Supposed to run in its own process.
    """
    def __read(self, stop_event):
        inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL)
        inp.setchannels(1)
        inp.setrate(self.__rate)
        inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        inp.setperiodsize(self.__period)

        while not stop_event.isSet():
            _, data = inp.read()
            self.__read_queue.put(data)

    """
    Runs the read and write processes.
    """
    def run(self):
	self.__stop = threading.Event()
        self.__read_thread = threading.Thread(target = self.__read, args=(self.__stop,))
        self.__read_thread.start()

    """
    Reads audio samples from the queue captured from the reading thread.
    """
    def read(self):
        return self.__read_queue.get()

    def clear(self):
	with self.__read_queue.mutex:
		return self.__read_queue.queue.clear()

    def close(self):
	self.__stop.set()


class AvsCallbacks(object):

	def __init__(self, player, avs):
		self.speak_directive = None
		self.play_directive = None
		self. alert_directive = None
		self.player = player
		self.avs = avs
		self.need_trigger = False
		self.avs.speech_synthesizer.speak_event += self.handle_speak
		self.avs.speech_recognizer.expect_speech_event += self.handle_expect_speech
		self.avs.audio_player.play_event += self.handle_music_play
		self.avs.audio_player.stop_event += self.handle_music_stop
		self.avs.speaker.set_volume_event += self.handle_volume
		self.avs.speaker.adjust_volume_event += self.handle_volume_adjust
		self.avs.alerts.set_alert_event += self.handle_set_alert


	def handle_speak(self, speak_directive):
		""" called when a speak directive is received from AVS """
		self.speak_directive = speak_directive
		if debug: print('Received a Speak directive from Alexa')

		# save the mp3 audio that AVS sent us as part of the Speak directive
		# pthread_resp = threading.Thread(target=write_file, args=('response.mp3', speak_directive.audio_data))
		# pthread_resp.start()
		with io.open('response.mp3', 'wb') as speak_file:
		    speak_file.write(speak_directive.audio_data)

		# self.player.play_audio(path + '/response.mp3', speak_directive=speak_directive)
		self.player.play(path + '/response.mp3', channel='dialog', directive=speak_directive)


	def handle_expect_speech(self, expect_request):
		self.need_trigger = True


	def handle_music_play(self, play_directive):
		"called when audioplayer directive is received from AVS"
		if debug: print('audio player directive recieved')
		stream = play_directive['audio_item']['stream']
		url = stream['url']
		content = mrl_fix(url)
		if debug: print('url', url)
		if play_directive.audio_data is not None:
			with io.open('flash.mp3', 'wb') as flash_file:
			    flash_file.write(play_directive.audio_data)
			self.player.play(path + '/flash.mp3', channel='dialog', directive=stream)
		else:
			pThread = threading.Thread(target=self.player.play, args=(content, 'content', stream))
			pThread.start()


	def handle_music_stop(self, stop_directive):
		"called when audioplayer directive is received from AVS"
		if debug: print('audio player directive recieved')
		if debug: print(stop_directive)
		self.player.stop()


	def handle_volume(self, volume_directive):
		"called when volume directive is received from avs"
		if debug: print(volume_directive)
		vol_token = volume_directive['volume']
		self.player.set_volume(int(vol_token))


	def handle_volume_adjust(self, volume_adj_directive):
		"called when volume adjustment directive is received from avs"
		if debug: print(volume_adj_directive)
		vol_token = volume_adj_directive['volume']
		self.player.set_volume(int(vol_token), adjust=True)


	def handle_set_alert(self, alert_directive):
		if debug: print(alert_directive)
		future_time = dateutil.parser.parse(alert_directive['scheduled_time'])
		u = datetime.utcnow()
		time_now = u.replace(tzinfo=pytz.utc)
		time_delta = future_time - time_now
		time_in_float = time_delta.total_seconds()
		if debug: print(time_in_float)
		threading.Timer(time_in_float, self.start_alert).start()


	def start_alert(self):
		if debug: print('playing alert')
		# TODO: pass 'alert' channel and implement in Player class
		self.player.play('alarm.wav')


def alexa_speech_recognizer(avs, audio_stream):
        avs.speech_recognizer.recognize(audio_data=audio_stream,
                                    profile='NEAR_FIELD')


def write_file(filename, payload):
	with open(filename, 'wb') as f:
		 f.write(payload)


def dialog_callback(event, avs, player, avs_callback, speak_directive=None):
	state = player.p_dialog.get_state()
	#0: 'NothingSpecial'
	#1: 'Opening'
	#2: 'Buffering'
	#3: 'Playing'
	#4: 'Paused'
	#5: 'Stopped'
	#6: 'Ended'
	#7: 'Error'
	if debug: print("{}Player State:{} {}".format(bcolors.OKGREEN, bcolors.ENDC, state))
	if state == 3:		#Playing
		if speak_directive is not None:
			player.set_background('content')
			if debug: print('notify avs stream started')
			avs.speech_synthesizer.speech_started(speak_directive.token)
	elif state == 5:	#Stopped
		player.dialog_playing = False
		player.set_foreground('content') # restore volume
		if speak_directive is not None:
			avs.speech_synthesizer.speech_finished(speak_directive.token)
	elif state == 6:	#Ended
		player.dialog_playing = False
		player.set_foreground('content') # restore volume
		if speak_directive is not None:
			avs.speech_synthesizer.speech_finished(speak_directive.token)
		if avs_callback.need_trigger:
		    avs_callback.need_trigger = False
		    if debug: print("Forcing Trigger")
		    fThread = threading.Thread(target=force_trigger)
		    fThread.start()


def report_content_progress_interval_to_avs(avs, player,token, interval):
	if player.content_playing:
		if debug: print('report interval progress to avs')
		offset_ms = player.p_content.get_time()
		if debug: print('current media offset ', offset_ms)
		avs.audio_player.progress_report_interval_elapsed(token, offset_ms)
		threading.Timer(interval, report_content_progress_interval_to_avs, [avs, player, token, interval]).start()


def report_content_progress_delay_to_avs(avs, player, token, interval):
	if player.content_playing:
		if debug: print('report delay progress to avs')
		offset_ms = player.p_content.get_time()
		if debug: print('current media offset ', offset_ms)
		avs.audio_player.progress_report_delay_elapsed(token, offset_ms)


def content_callback(event, avs, player, avs_callback, stream):
	if debug: print(stream)
	state = player.p_content.get_state()
	#0: 'NothingSpecial'
	#1: 'Opening'
	#2: 'Buffering'
	#3: 'Playing'
	#4: 'Paused'
	#5: 'Stopped'
	#6: 'Ended'
	#7: 'Error'
	if debug: print("{}Player State:{} {}".format(bcolors.OKGREEN, bcolors.ENDC, state))
	if state == 3:		#Playing
		if stream is not None:
			if debug: print('notify avs stream started')
			offset_ms = player.p_content.get_time()
			if debug: print('offset when starting the stream:', offset_ms)
			avs.audio_player.playback_started(stream['token'], offset_ms)
			# avs.audio_player.progress_report_interval_elapsed(stream['token'], offset_ms)
			report_delay_secs = stream['progressReport']['progressReportDelayInMilliseconds']/1e3
			report_interval_secs = stream['progressReport']['progressReportIntervalInMilliseconds']/1e3
			#FIXME: have to report more frequently for some reason - 6 seems to be the magic number
			report_interval_secs = report_interval_secs/6
			if debug: print('report_delay_secs: ',report_delay_secs)
			if debug: print('report_interval_secs: ',report_interval_secs)
			threading.Timer(report_delay_secs, report_content_progress_delay_to_avs, [avs, player, stream['token'], report_delay_secs]).start()
			threading.Timer(report_interval_secs, report_content_progress_interval_to_avs, [avs, player, stream['token'], report_interval_secs]).start()

	elif state == 5:	#Stopped
		if debug: print('player stopped')
		player.content_playing = False
		# TODO : need to pass offset_ms before player is stopped
		offset_ms = 0L #player.p_content.get_time() 
		if stream is not None:
			if debug:print('notify avs player stopped')
			avs.audio_player.playback_stopped(stream['token'], offset_ms)
		player.p_content = ""
	elif state == 6:	#Ended
		player.content_playing = False
		offset_ms = 0
		if player.p_content != '':
			offset_ms = 0
			offset_ms = player.p_content.get_time()
		if stream is not None:
			avs.audio_player.playback_stopped(stream['token'],offset_ms)
		player.p_content = ""
	elif state == 7:
		player.content_playing = False


def meta_callback(event, content):
	title = content.get_meta(vlc.Meta.Title)
	artist = content.get_meta(vlc.Meta.Artist)
	album = content.get_meta(vlc.Meta.Album)
	tracknumber = content.get_meta(vlc.Meta.TrackNumber)
	url = content.get_meta(vlc.Meta.URL)
	nowplaying = content.get_meta(vlc.Meta.NowPlaying)
	if debug: print('{}Title:{} {}'.format(bcolors.OKBLUE, bcolors.ENDC, title))
	if debug: print('{}Artist:{} {}'.format(bcolors.OKBLUE, bcolors.ENDC, artist))
	if debug: print('{}Album:{} {}'.format(bcolors.OKBLUE, bcolors.ENDC, album))
	if debug: print('{}Track:{} {}'.format(bcolors.OKBLUE, bcolors.ENDC, tracknumber))
	if debug: print('{}Url:{} {}'.format(bcolors.OKBLUE, bcolors.ENDC, url))
	if debug: print('{}Now Playing:{} {}'.format(bcolors.OKBLUE, bcolors.ENDC, nowplaying))


def format_time(self, milliseconds):
	"""formats milliseconds to h:mm:ss
	"""
	self.position = milliseconds / 1000
	m, s = divmod(self.position, 60)
	h, m = divmod(m, 60)
	return "%d:%02d:%02d" % (h, m, s)


def generate_audio(audio, rf):
	data_stream = b''
	while(GPIO.input(button)==1): # we keeplayer.p_dialogrecording while the button is pressed
		data = audio.read()
		yield data
		data_stream += data

	rf.write(data_stream)


def record_multiple(directory=None):
	"for testing - records long/multiple queries without stopping"
	audio = Audio()
	channel = GPIO.wait_for_edge(button, GPIO.RISING, bouncetime=1) # we wait for the button to be pressed
	audio.run()
	if channel is not None:
		print("{}Recording...{}".format(bcolors.OKBLUE, bcolors.ENDC))
		rf = open(path+'recording.wav', 'w')
		while True:
			try:
				data = audio.read()
				rf.write(data)
			except KeyboardInterrupt:
				if directory is not None:
					timestr = time.strftime("%H%M%S")
					copyfile(path+'recording.wav', directory+'/'+'query_'+timestr+'.wav') 
				rf.close()
				audio.close()
				print('Threads killed sucessfully')
				break



def start(directory=None, noavs=False, audio_file=None):

	with io.open(_CONFIG_PATH, 'r') as cfile:
		config = yaml.load(cfile)

	# AvsClient requires a dict with client_id, client_secret, refresh_token
	avs = simpleavs.AvsClient(config)

	if debug: print('Connecting to AVS')
	avs.connect()

	player = Player(dialog_callback=dialog_callback, content_callback=content_callback, avs=avs)

	avs_callback_handler = AvsCallbacks(player, avs) 
	player.avs_callback = avs_callback_handler

	player.play(path+"hello.mp3", channel='dialog')

	# avs = set_avs_callback_handlers(avs)
	print("{}Ready to Record.{}".format(bcolors.OKBLUE, bcolors.ENDC))
	volume = None
	audio = Audio()
	audio.run()

	while True:
		try:
			if audio_file is not None:
				player.play(audio_file, channel='dialog')
			# adding a timeout to keeplayer.p_dialogthe thread alive.. or else cannot use keyboard to kill the program
			# also clear the audio queue every 1 sec if not triggered
			channel = GPIO.wait_for_edge(button, GPIO.RISING, bouncetime=1, timeout=1000) # we wait for the button to be pressed
			audio.clear()
			if channel is not None:
				player.stop(channel='dialog') # stop current response if user interrupts
				player.set_background('content')
				print("{}Recording...{}".format(bcolors.OKBLUE, bcolors.ENDC))

				rf = open(path+'recording.wav', 'w')
				data = generate_audio(audio, rf)
				alexa_speech_recognizer(avs, data)
				print("{}Recording Finished.{}".format(bcolors.OKBLUE, bcolors.ENDC))

				rf.close()
				if directory is not None:
					timestr = time.strftime("%H%M%S")
					copyfile(path+'recording.wav', directory+'/'+'query_'+timestr+'.wav') 

				player.set_foreground('content')

			audio.clear()
		except KeyboardInterrupt:
			audio.close()
			avs.disconnect()
			print('Threads killed sucessfully')
			break


def setup():
	GPIO.setwarnings(False)
	GPIO.cleanup()
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

	while internet_on() == False:
		print(".")


def create_recording_dir():
	timestr = time.strftime("rec_%d%m%Y")
	directory = 'recordings/'+timestr
	if not os.path.exists(directory):
	    os.makedirs(directory)
        return directory


def force_trigger(trigger_infinite=False):
    pass


if __name__ == "__main__":
	args = docopt(__doc__, version='0.1')
	setup()
	directory = None
	noavs=False
	audio_file=None
	if args['--debug'] is True: 
		debug = 1
	if args['--saverecordings'] is True: 
		directory = create_recording_dir()
	if args['noavs'] is True:
		noavs=True
	if args['--play'] is not None:
		audio_file=args['--play']
	if args['--record-multiple'] == True:
		record_multiple(directory=directory)
	if noavs == False:
		start(directory=directory, noavs=noavs, audio_file=audio_file)

