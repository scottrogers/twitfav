#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2012 Gustav Arngården

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# consts
CONSUMER_KEY = "###"
CONSUMER_SECRET = "###"
ACCESS_TOKEN = "######"
ACCESS_TOKEN_SECRET = "###"
TRACK_TERMS = "search, terms"
# TRACK_TERMS = "restaurants, horrible restaurant sites, websites"
import sys
import time
import pycurl
import urllib
import json
import oauth2 as oauth
import urllib2

SEARCH_ENDPOINT_URL = "https://api.twitter.com/1.1/search/tweets.json"
API_ENDPOINT_URL = 'https://stream.twitter.com/1.1/statuses/filter.json'
FAV_ENDPOINT_URL = 'https://api.twitter.com/1.1/favorites/create.json'

USER_AGENT = 'Smelker Pot 1.0' # This can be anything really

# You need to replace these with your own values
OAUTH_KEYS = {'consumer_key': CONSUMER_KEY,
              'consumer_secret': CONSUMER_SECRET,
              'access_token_key': ACCESS_TOKEN,
              'access_token_secret': ACCESS_TOKEN_SECRET}

# These values are posted when setting up the connection
POST_PARAMS = {'include_entities': 0,
               'stall_warning': 'true',
               'track': TRACK_TERMS}

class TwitterStream:
    def __init__(self, timeout=False):
        self.oauth_token = oauth.Token(key=OAUTH_KEYS['access_token_key'], secret=OAUTH_KEYS['access_token_secret'])
        self.oauth_consumer = oauth.Consumer(key=OAUTH_KEYS['consumer_key'], secret=OAUTH_KEYS['consumer_secret'])
        self.conn = None
        self.buffer = ''
        self.timeout = timeout
        self.setup_connection()

    def setup_connection(self):
        """ Create persistant HTTP connection to Streaming API endpoint using cURL.
        """
        if self.conn:
            self.conn.close()
            self.buffer = ''
        self.conn = pycurl.Curl()
        # Restart connection if less than 1 byte/s is received during "timeout" seconds
        if isinstance(self.timeout, int):
            self.conn.setopt(pycurl.LOW_SPEED_LIMIT, 1)
            self.conn.setopt(pycurl.LOW_SPEED_TIME, self.timeout)
        self.conn.setopt(pycurl.URL, API_ENDPOINT_URL)
        self.conn.setopt(pycurl.USERAGENT, USER_AGENT)
        # Using gzip is optional but saves us bandwidth.
        self.conn.setopt(pycurl.ENCODING, 'deflate, gzip')
        self.conn.setopt(pycurl.POST, 1)
        self.conn.setopt(pycurl.POSTFIELDS, urllib.urlencode(POST_PARAMS))
        self.conn.setopt(pycurl.HTTPHEADER, ['Host: stream.twitter.com',
                                             'Authorization: %s' % self.get_oauth_header()])
        # self.handle_tweet is the method that are called when new tweets arrive
        self.conn.setopt(pycurl.WRITEFUNCTION, self.handle_tweet)

    def get_oauth_header(self):
        """ Create and return OAuth header.
        """
        params = {'oauth_version': '1.0',
                  'oauth_nonce': oauth.generate_nonce(),
                  'oauth_timestamp': int(time.time())}
        req = oauth.Request(method='POST', parameters=params, url='%s?%s' % (API_ENDPOINT_URL,
                                                                             urllib.urlencode(POST_PARAMS)))
        req.sign_request(oauth.SignatureMethod_HMAC_SHA1(), self.oauth_consumer, self.oauth_token)
        return req.to_header()['Authorization'].encode('utf-8')

    def start(self):
        """ Start listening to Streaming endpoint.
        Handle exceptions according to Twitter's recommendations.
        """
        backoff_network_error = 0.25
        backoff_http_error = 5
        backoff_rate_limit = 60
        while True:
            self.setup_connection()
            try:
                self.conn.perform()
            except:
                # Network error, use linear back off up to 16 seconds
                print 'Network error: %s' % self.conn.errstr()
                print 'Waiting %s seconds before trying again' % backoff_network_error
                time.sleep(backoff_network_error)
                backoff_network_error = min(backoff_network_error + 1, 16)
                continue
            # HTTP Error
            sc = self.conn.getinfo(pycurl.HTTP_CODE)
            if sc == 420:
                # Rate limit, use exponential back off starting with 1 minute and double each attempt
                print 'Rate limit, waiting %s seconds' % backoff_rate_limit
                time.sleep(backoff_rate_limit)
                backoff_rate_limit *= 2
            else:
                # HTTP error, use exponential back off up to 320 seconds
                print 'HTTP error %s, %s' % (sc, self.conn.errstr())
                print 'Waiting %s seconds' % backoff_http_error
                time.sleep(backoff_http_error)
                backoff_http_error = min(backoff_http_error * 2, 320)

    def handle_tweet(self, data):
        # print data
        """ This method is called when data is received through Streaming endpoint.
        """
        self.buffer += data
        if data.endswith('\r\n') and self.buffer.strip():
            # complete message received
            message = json.loads(self.buffer)

            self.buffer = ''
            msg = ''
            if message.get('limit'):
                print 'Rate limiting caused us to miss %s tweets' % (message['limit'].get('track'))
            elif message.get('disconnect'):
                raise Exception('Got disconnect: %s' % message['disconnect'].get('reason'))
            elif message.get('warning'):
                print 'Got warning: %s' % message['warning'].get('message')
            else:
                if message.get('lang') == 'en' and message.get('text')[0] != '@':
                    followers = float(message.get('user')['followers_count'])
                    following = float(message.get('user')['friends_count'])
                    print "Followers: " + str(followers)
                    print "Following: " + str(following)

                    if followers != 0:
                      if following/followers >= .25:
                        print str(message.get('id')) + ": " + message.get('text')
                        with open('tweets.json', 'a') as f:
                            f.write(str(message.get('id')) + ', ')

                        f.close()
                      else:
                        print str(message.get('id')) + ": They are too popular, probably wont folow you. Fuck 'em."


                # return 0

    def get_oauth_header_favs(self, tweet_id):
        fav_post_params = {'id': tweet_id }

        """ Create and return OAuth header.
        """
        params = {'oauth_version': '1.0',
                  'oauth_nonce': oauth.generate_nonce(),
                  'oauth_timestamp': int(time.time())}

        req = oauth.Request(method='POST', parameters=params, url='%s?%s' % (FAV_ENDPOINT_URL,
                                                                             urllib.urlencode(fav_post_params)))
        req.sign_request(oauth.SignatureMethod_HMAC_SHA1(), self.oauth_consumer, self.oauth_token)
        return req.to_header()['Authorization'].encode('utf-8')


    def favorite_tweet(self):

        def _fav_tweet(tweet_id, messages_file):
          twitter_auth = self.get_oauth_header_favs(tweet_id)

          url = FAV_ENDPOINT_URL
          req = urllib2.Request(url, data="id=" + tweet_id)

          req.add_header('Authorization', "%s" % twitter_auth)
          req.add_header('Host', 'api.twitter.com')
          req.add_header('Content-Type', 'application/x-www-form-urlencoded')

          try:
              resp = urllib2.urlopen(req)
              print "Favorited ID: " + tweet_id
              tweet = resp.read()
              # messages = json.loads(unicode(new_data, "ISO-8859-1"))
              tweet_dict = json.loads(tweet)
              print tweet_dict.get('text')



          except urllib2.HTTPError, e:
              print e
              print e.code
              print e.msg
              print e.headers
              print e.fp.read()

        f = open("tweets.json", 'r')
        messages_file = f.read()

        messages = messages_file.split(', ')
        print "Going through " + str(len(messages)) + " tweets."

        for message in messages:
          fav = _fav_tweet(str(message), messages_file)

        f.close()

        f = open('tweets.json', 'w')
        f.write('')
        f.close()
        return False



# print 'Number of arguments:', len(sys.argv), 'arguments.'
# print 'Argument List:', str(sys.argv)

ts = TwitterStream()

if sys.argv[1] == 'run':
  print "Looking for tweets..."
  ts.setup_connection()
  ts.start()

if sys.argv[1] == 'fav':
  print "Favoriting tweets..."
  ts.favorite_tweet()
