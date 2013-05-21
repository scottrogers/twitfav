#!/usr/bin/python
# -*- coding: utf-8 -*-

# You need to replace these with your own values
CONSUMER_KEY = "REPLACE"
CONSUMER_SECRET = "REPLACE"
ACCESS_TOKEN = "REPLACE"
ACCESS_TOKEN_SECRET = "REPLACE"
TRACK_TERMS = "replace, with, search, terms"


import time
import pycurl
import urllib
import json
import oauth2 as oauth
import urllib2


API_ENDPOINT_URL = 'https://stream.twitter.com/1.1/statuses/filter.json'
FAV_ENDPOINT_URL = 'https://api.twitter.com/1.1/favorites/create.json'

USER_AGENT = 'TwitterStream 1.0' # This can be anything really

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
        self.conn.setopt(pycurl.ENCODING, 'deflate, gzip')
        self.conn.setopt(pycurl.POST, 1)
        self.conn.setopt(pycurl.POSTFIELDS, urllib.urlencode(POST_PARAMS))
        self.conn.setopt(pycurl.HTTPHEADER, ['Host: stream.twitter.com',
                                             'Authorization: %s' % self.get_oauth_header()])
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
                if message.get('lang') == 'en':
                    print message.get('text')
                    fav = self.favorite_tweet(message.get('id'))

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

    def favorite_tweet(self, tweet_id):

        fav_post_params = {'id': tweet_id}
        """ resign token for favoriting tweet
        """
        twitter_auth = self.get_oauth_header_favs(tweet_id)

        url = FAV_ENDPOINT_URL
        req = urllib2.Request(url, data="id=" + str(tweet_id))

        req.add_header('Authorization', "%s" % twitter_auth)
        req.add_header('Host', 'api.twitter.com')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        try:
            resp = urllib2.urlopen(req)

        except urllib2.HTTPError, e:
            print e
            print e.code
            print e.msg
            print e.headers
            print e.fp.read()

ts = TwitterStream()
ts.setup_connection()
ts.start()