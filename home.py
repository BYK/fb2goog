# coding: utf-8

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import os
import sys

sys.setrecursionlimit(10000) # SDK fix


class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        
        path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
        self.response.out.write(template.render(path, None))

    def put(self):
        pass


application = webapp.WSGIApplication([
                ('/', MainPage)
              ],
              debug=True)


def main():
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
