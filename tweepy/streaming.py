# Tweepy
# Copyright 2009-2010 Joshua Roesslein
# See LICENSE for details.

import httplib
from socket import timeout
from threading import Thread
from time import sleep
import urllib

from tweepy.models import Status
from tweepy.api import API
from tweepy.error import TweepError

from tweepy.utils import import_simplejson
json = import_simplejson()

STREAM_VERSION = 1


class StreamListener(object):

    def __init__(self, api=None):
        self.api = api or API()

    def on_data(self, data):
        """Called when raw data is received from connection.

        Override this method if you wish to manually handle
        the stream data. Return False to stop stream and close connection.
        """

        if 'in_reply_to_status_id' in data:
            status = Status.parse(self.api, json.loads(data))
            if self.on_status(status) is False:
                return False
        elif 'delete' in data:
            delete = json.loads(data)['delete']['status']
            if self.on_delete(delete['id'], delete['user_id']) is False:
                return False
        elif 'limit' in data:
            if self.on_limit(json.loads(data)['limit']['track']) is False:
                return False

    def on_status(self, status):
        """Called when a new status arrives"""
        return

    def on_delete(self, status_id, user_id):
        """Called when a delete notice arrives for a status"""
        return

    def on_limit(self, track):
        """Called when a limitation notice arrvies"""
        return

    def on_error(self, status_code):
        """Called when a non-200 status code is returned"""
        return False

    def on_timeout(self):
        """Called when stream connection times out"""
        return


class Stream(object):

    host = 'stream.twitter.com'

    def __init__(self, auth, listener, **options):
        self.auth = auth
        self.listener = listener
        self.running = False
        self.timeout = options.get("timeout", 300.0)
        self.retry_count = options.get("retry_count")
        self.retry_time = options.get("retry_time", 10.0)
        self.snooze_time = options.get("snooze_time",  5.0)
        self.buffer_size = options.get("buffer_size",  1500)
        if options.get("secure", True):
            self.scheme = "https"
        else:
            self.scheme = "http"

        self.api = API()
        self.headers = options.get("headers") or {}
        self.parameters = None
        self.body = None
        #self.custom_read_loop = True #added to differentiate between original and modified self._read_loop()


    def _run(self):
        # Authenticate
        url = "%s://%s%s" % (self.scheme, self.host, self.url)

        # Connect and process the stream
        error_counter = 0
        conn = None
        exception = None
        while self.running:
            if self.retry_count is not None and error_counter > self.retry_count:
                # quit if error count greater than retry count
                break
            try:
                if self.scheme == "http":
                    conn = httplib.HTTPConnection(self.host)
                else:
                    conn = httplib.HTTPSConnection(self.host)
                self.auth.apply_auth(url, 'POST', self.headers, self.parameters)
                conn.connect()
                conn.sock.settimeout(self.timeout)
                conn.request('POST', self.url, self.body, headers=self.headers)
                resp = conn.getresponse()
                if resp.status != 200:
                    if self.listener.on_error(resp.status) is False:
                        break
                    error_counter += 1
                    sleep(self.retry_time)
                else:
                    error_counter = 0
                    self._read_loop3(resp)
                    #if self.custom_read_loop == False:
	            #    self._read_loop(resp)
	            #else:
	            #    self._read_loop3(resp)
            except timeout:
                if self.listener.on_timeout() == False:
                    break
                if self.running is False:
                    break
                conn.close()
                sleep(self.snooze_time)
            except Exception, exception:
                # any other exception is fatal, so kill loop
                break

        # cleanup
        self.running = False
        if conn:
            conn.close()

        if exception:
            raise

    def _data(self, data):
        for d in [dt for dt in data.split('\n') if dt]:
            if self.listener.on_data(d) is False:
                self.running = False

    class jsonengine():
        def __init__(self, json, object_callback):
#            import sys
            self.json = json
            self.buf = ''
#            self.w = sys.stdout.write
            self.objectsprocessed = 0
            self.object_callback = object_callback
        
        def on_obj(self, jobj):
            #replace this in subclass? no...
            print "object processing index:%d" % self.objectsprocessed
            self.objectsprocessed = self.objectsprocessed + 1
            try:
	            success = self.object_callback(jobj)
	            if success == False:
	            	print "obect_callback reported that the object failed execution\n"
	            elif success == True: 
	            	print "object_callback reported that the object succeeded execution\n"
	    except:
	    	    print "exception in processing jobj caught in on_obj in jsonengine\n"
        
        def unescape(self, char):
        	if char == '\n': return "\\n"
        	if char == '\t': return "\\t"
        	if char == ' ': return "space"
        	if char == '\r': return "\\r"
        	else: return char
        
        def input_char(self, char):
            #print self.buf, len(self.buf), self.unescape(char), ord(char)
            if char == '\r':
                print "\\r type detected, processing self.buf...",
                if len(self.buf) == 0:
                    print "self.buf was empty"
                else:
                    print "there's something in the buffer...?"
                    o = self.json.loads(self.buf)
                    self.buf = ''
                    self.on_obj(o)
            elif char != '\n':
                self.buf = self.buf + char


#    def _onjson(self, jobj):
#    	print jobj

    def _read_loop3(self, resp):
    	while self.running and not resp.isclosed():
    		self.listener.recievechar(resp.read(amt=1))
    	if resp.isclosed():
    		self.onclosed(resp)

    def _read_loop2(self, resp):
        import ujson as json
        j = self.jsonengine(json, self.listener.on_jsonobject)
        while self.running and not resp.isclosed():
            j.input_char(resp.read(amt=1))
        if resp.isclosed():
            self.on_closed(resp)

    def _read_loop(self, resp):
        buf = ''
        while self.running and not resp.isclosed():
            c = resp.read(self.buffer_size)
            idx = c.rfind('\n')
            if idx > -1:
                # There is an index. Store the tail part for later,
                # and process the head part as messages. We use idx + 1
                # as we dont' actually want to store the newline.
                data = buf + c[:idx]
                buf = c[idx + 1:]
                self._data(data)
            else:
                # No newline found, so we add this to our accumulated
                # buffer
                buf += c

        if resp.isclosed():
            self.on_closed(resp)


    def _start(self, async):
        self.running = True
        if async:
            Thread(target=self._run).start()
        else:
            self._run()

    def on_closed(self, resp):
        """ Called when the response has been closed by Twitter """
        pass

    def userstream(self, count=None, async=False, secure=True):
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/2/user.json'
        self.host='userstream.twitter.com'
        if count:
            self.url += '&count=%s' % count
        self.custom_read_loop = True #added in order to activate self._read_loop2() in self._run()
        self._start(async)

    def firehose(self, count=None, async=False):
        self.parameters = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%i/statuses/firehose.json?delimited=length' % STREAM_VERSION
        if count:
            self.url += '&count=%s' % count
        self._start(async)

    def retweet(self, async=False):
        self.parameters = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%i/statuses/retweet.json?delimited=length' % STREAM_VERSION
        self._start(async)

    def sample(self, count=None, async=False):
        self.parameters = {'delimited': 'length'}
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%i/statuses/sample.json?delimited=length' % STREAM_VERSION
        if count:
            self.url += '&count=%s' % count
        self._start(async)

    def filter(self, follow=None, track=None, async=False, locations=None, count = None):
        self.parameters = {}
        self.headers['Content-type'] = "application/x-www-form-urlencoded"
        if self.running:
            raise TweepError('Stream object already connected!')
        self.url = '/%i/statuses/filter.json?delimited=length' % STREAM_VERSION
        if follow:
            self.parameters['follow'] = ','.join(map(str, follow))
        if track:
            self.parameters['track'] = ','.join(map(str, track))
        if locations and len(locations) > 0:
            assert len(locations) % 4 == 0
            self.parameters['locations'] = ','.join(['%.2f' % l for l in locations])
        if count:
            self.parameters['count'] = count
        self.body = urllib.urlencode(self.parameters)
        self.parameters['delimited'] = 'length'
        self._start(async)

    def disconnect(self):
        if self.running is False:
            return
        self.running = False

