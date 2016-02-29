#!/usr/bin/env python

from __future__ import print_function

import re
import irc.bot
import logging
from time import time
from random import random

if hasattr(__builtins__, 'xrange'):
	range = xrange

FLOURISH = r'(?:feliciaBoom|<3|gandsLessThanThree|feliciaHeart|g33kLove|g33kHugs|hrpgLoveyousortof)'

# TODO: match "/me waves at all" etc.
GREETING = \
	r"(?:(?:also,|quick)?\s+)?(?:(?:ay|oi|ole|ha*i+|hey+|heys+|hia+|hiya+|hi-?ya+|high|heya+|heyo+|h[eau]llo+|hola+|howdy+doo+dy+|greetings+|howdy+|welcome(?:\s+back)?|(?:what)?'?s\s*up(?:\s*dog+)?|what\s*up(?:\s*dog+)?|howdy-?do+|yo+|wh?add?\s*up(?:\s*dog+)?|yuhu+|good\s*day|g'?\s*day)\s*)+(?:to|there)?"

RE_GENERAL_GREETING = re.compile(
	r'^\s*(?:' + FLOURISH + '\s+)*' + GREETING +
	r'(?:\s+(?:all|everyone|everybody|weirdos|suckers|fuckers|hoomans|people|ppl|again|chat))?\s*'+
	r'[\.!\?]*(?:\s+' + FLOURISH + ')*\s*$', re.I)

RE_GREETING = re.compile(
	r'^\s*(?:' + FLOURISH + '\s+)*' + GREETING + r'(?:\s*,\s*|\s+)(.*?)\s*[\.!\?]*\s*$', re.I)

COLLECTIVE_NICKALIAS = [
	'all', 'everyone', 'everybody', 'weirdos', 'suckers', 'fuckers', 'hoomans', 'people', 'ppl', 'chat'
]

logger = logging.getLogger('hibot')

def normalize_nick(alias):
	return alias.strip().lower()

class HiBot(irc.bot.SingleServerIRCBot):
	def __init__(self, nickname, channels, nickalias=None, password=None, server='irc.twitch.tv', port=6667, greet_timeout=3600, greet_delay=3, greet_delay_random=2, proxyusers=None):
		irc.bot.SingleServerIRCBot.__init__(self, [(server, port, password)], nickname, nickname)
		self.join_channels      = [channel if channel.startswith('#') else '#'+channel for channel in channels]
		self._nickalias         = set(tuple(normalize_nick(nick).split()) for nick in nickalias) if nickalias is not None else set()
		self.greeted            = {}
		self.greet_timeout      = greet_timeout
		self.greet_delay        = greet_delay
		self.greet_delay_random = greet_delay_random
		self.proxyusers         = proxyusers if proxyusers is not None else {'ytchat'}

		norm_nick = normalize_nick(nickname)
		self._nickalias.add((norm_nick,))
		self._nickalias.add(('@'+norm_nick,))
		for alias in COLLECTIVE_NICKALIAS:
			self._nickalias.add((alias,))
		self._max_alias_len = max(len(alias) for alias in self._nickalias)

		self._hi_queue = {}
		self._hi_queued = False

	def on_welcome(self, connection, event):
		for channel in self.join_channels:
			connection.join(channel)

	def on_nicknameinuse(self, connection, event):
		logger.error('nickname in use')

	def on_error(self, connection, event):
		logger.error(' '.join(event.arguments))

	def on_pubmsg(self, connection, event):
		norm_nick   = normalize_nick(self.connection.get_nickname())
		sender      = event.source.nick
		message     = event.arguments[0]
		now         = time()

		if sender in self.proxyusers:
			x = message.split(':',1)
			if len(x) == 2:
				sender, message = x
				sender = sender.strip()

		norm_sender = normalize_nick(sender)

		if norm_sender == norm_nick:
			match = RE_GREETING.match(message)
			if match:
				for nick in normalize_nick(match.group(1)).replace(',',' ').split():
					if nick.startswith('@'):
						nick = nick[1:]
					elif nick == 'and':
						continue
					self.greeted[nick] = now

		elif now - self.greeted.get(norm_sender, 0) > self.greet_timeout:
			match = RE_GENERAL_GREETING.match(message)
			if match:
				self._queue_hi(sender, event.target)
				return

			match = RE_GREETING.match(message)
			if match:
				nicks = normalize_nick(match.group(1)).replace(',',' ').split()
				if self._contains_alias(nicks):
					self._queue_hi(sender, event.target)
					return

	def _contains_alias(self, nicks):
		nicks_len = len(nicks)
		for alias_len in range(1,self._max_alias_len + 1):
			for i in range(0,nicks_len - alias_len + 1):
				if tuple(nicks[i:i + alias_len]) in self._nickalias:
					return True
		return False

	def _queue_hi(self, sender, channel):
		if channel in self._hi_queue:
			self._hi_queue[channel].add(sender)
		else:
			self._hi_queue[channel] = {sender}

		if not self._hi_queued:
			self.connection.execute_delayed(self.greet_delay + (random() - 0.5) * self.greet_delay_random, self._perform_queued_hi)
			self._hi_queued = True

	def _perform_queued_hi(self):
		self._hi_queued = False
		for channel in self._hi_queue:
			self._say_hi(self._hi_queue[channel], channel)
		self._hi_queue.clear()

	def _say_hi(self, senders, channel):
		msg = ["Hi "]
		senders = sorted('@'+sender for sender in senders)
		if len(senders) > 1:
			msg.append(', '.join(senders[:-1]))
			msg.append(', and ')
		msg.append(senders[-1])
		msg.append('!')
		msg = ''.join(msg)

		self.connection.privmsg(channel, msg)
		for sender in senders:
			self.greeted[normalize_nick(sender)] = time()
		logger.info('greeted %s' % ', '.join(senders))

def main(args):
	import yaml
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument('-c','--config',default='config.yaml')
	parser.add_argument('-l','--log-level',type=int,default=0)
	opts = parser.parse_args(args)

	logger.setLevel(opts.log_level)

	with open(opts.config,'rb') as fp:
		config = yaml.load(fp)

	server, port = config.get('host','irc.twitch.tv:6667').split(':',1)
	port = int(port)

	bot = HiBot(
		config['nickname'],
		config['channels'],
		config.get('nickalias'),
		config.get('password'),
		server,
		port,
		config.get('greet_timeout',3600),
		config.get('greet_delay',3),
		config.get('greet_delay_random',3),
		config.get('proxyusers',{'ytchat'}))
	bot.start()

if __name__ == '__main__':
	import sys

	try:
		main(sys.argv[1:])
	except KeyboardInterrupt:
		print()
