#!/usr/bin/env python
#
# Copyright 2015 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import jinja2
import os
import cloudstorage as gcs
import logging
import webapp2

from google.appengine.ext import ndb

BUCKET_NAME = 'your_bucket_name'

MY_DEFAULT_RETRY_PARAMS = gcs.RetryParams(initial_delay=0.2,
                                          max_delay=5.0,
                                          backoff_factor=2,
                                          max_retry_period=15)
gcs.set_default_retry_params(MY_DEFAULT_RETRY_PARAMS)


def guestbook_key(guestbook_name='default_guestbook'):
    return ndb.Key('Guestbook', guestbook_name)

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Greeting(ndb.Model):
    content = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)


class MainPage(webapp2.RequestHandler):
    def get(self):
        greetings_query = Greeting.query(
            ancestor=guestbook_key()).order(-Greeting.date)
        greetings = greetings_query.fetch(10)
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(entries=greetings))

    def post(self):
        greeting = Greeting(parent=guestbook_key())
        greeting.content = self.request.get('entry')
        greeting.put()

        filename = '/' + BUCKET_NAME + '/' + str(greeting.date)
        content = str(greeting.content)

        try:
            self.create_file(filename, content)

        except Exception, error:
            logging.exception(error)
            self.delete_file(filename)

        else:
            logging.info('The object was created in Google Cloud Storage')
        self.redirect('/')

    def create_file(self, filename, content):
        write_retry_params = gcs.RetryParams(backoff_factor=1.1)
        gcs_file = gcs.open(filename,
                            'w',
                            content_type='text/plain',
                            retry_params=write_retry_params)
        gcs_file.write(content)
        gcs_file.close()

    def delete_file(self, filename):
        try:
            gcs.delete(filename)
        except gcs.NotFoundError:
            pass
        logging.info('There was an error writing to Google Cloud Storage')


class Clear(webapp2.RequestHandler):
    def post(self):
        greetings_query = Greeting.query(
            ancestor=guestbook_key()).fetch(keys_only=True)
        ndb.delete_multi(greetings_query)
        self.redirect('/')

application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/clear', Clear),
], debug=True)
