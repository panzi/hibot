#!/usr/bin/env python

from __future__ import print_function

import re
import irc.bot
from time import time

if hasattr(__builtins__, 'xrange'):
	range = xrange

FLOURISH = r'(?:feliciaBoom|<3|gandsLessThanThree)'

GREETING = \
	r"(?:hi+|hey+|hia+|hi-?ya+|heya+|heyo+|h[eau]llo+|greetings+|howdy+|welcome(?:\s+back)?|(?:what)?'?s\s*up(?:\s*dog+)|what\s*up(?:\s*dog+)?|howdy-?do+|yo|wh?add?\s*up(?:\s*dog+)?|yuhu+|good\s*day|'?g\s*day)"

RE_GENERAL_GREETING = re.compile(
	r'^\s*(?:' + FLOURISH + '\s+)*' + GREETING +
	r'(?:\s+(?:all|everyone|everybody|weirdos|suckers|fuckers|hoomans|people|ppl|again|chat))?\s*'+
	r'[\.!?]*(?:\s+' + FLOURISH + ')*\s*$', re.I)

RE_GREETING = re.compile(
	r'^\s*(?:' + FLOURISH + '\s+)*' + GREETING + r'\s+(?:,\s*)?(.*?)\s*[\.!?]*\s*$', re.I)

def normalize_nick(alias):
	return alias.strip().lower()

class HiBot(irc.bot.SingleServerIRCBot):
	def __init__(self, nickname, channels, nickalias=None, password=None, server='irc.twitch.tv', port=6667, greet_timeout=3600):
		irc.bot.SingleServerIRCBot.__init__(self, [(server, port, password)], nickname, nickname)
		self.join_channels = [channel if channel.startswith('#') else '#'+channel for channel in channels]
		self.nickalias     = set(tuple(normalize_nick(nick).split()) for nick in nickalias) if nickalias is not None else set()
		self.greeted       = {}
		self.greet_timeout = greet_timeout

		norm_nick = normalize_nick(nickname)
		self.nickalias.add((norm_nick,))
		self.nickalias.add(('@'+norm_nick,))

	def on_welcome(self, connection, event):
		for channel in self.join_channels:
			connection.join(channel)

	def on_nicknameinuse(self, connection, event):
		print('error: nickname in use')

	def on_error(self, connection, event):
		print('error: %s' % ' '.join(event.arguments))

	def on_pubmsg(self, connection, event):
		norm_nick   = normalize_nick(self.connection.get_nickname())
		sender      = event.source.nick
		norm_sender = normalize_nick(sender)
		message     = event.arguments[0]
		now         = time()

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
				self._say_hi(sender, event.target)
				return

			match = RE_GREETING.match(message)
			if match:
				nicks = normalize_nick(match.group(1)).replace(',',' ').split()
				if self._contains_alias(nicks):
					self._say_hi(sender, event.target)
					return

	def _contains_alias(self, nicks):
		for alias in self.nickalias:
			alias_len = len(alias)
			for i in range(0,len(nicks),alias_len):
				if alias == tuple(nicks[i:i+alias_len]):
					return True
		return False

	def _say_hi(self, sender, channel):
		self.connection.privmsg(channel, "Hi @%s!" % sender)
		self.greeted[normalize_nick(sender)] = time()

def main(args):
	import yaml
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument('-c','--config',default='config.yaml')
	opts = parser.parse_args(args)

	with open(opts.config,'rb') as fp:
		config = yaml.load(fp)

	server, port = config.get('host','irc.twitch.tv:6667').split(':',1)
	port = int(port)
	greet_timeout = config.get('greet_timeout',3600)

	bot = HiBot(
		config['nickname'],
		config['channels'],
		config.get('nickalias'),
		config.get('password'),
		server,
		port,
		greet_timeout)
	bot.start()

if __name__ == '__main__':
	import sys

	try:
		main(sys.argv[1:])
	except KeyboardInterrupt:
		print()
