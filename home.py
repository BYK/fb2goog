# coding: utf-8

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import db

import os
import sys
import zipfile
from StringIO import StringIO

sys.setrecursionlimit(10000) # SDK fix

class MainPage(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'

		user = users.get_current_user()

		if user:
			url = users.create_logout_url(self.request.uri)
			is_logged = True
		else:
			url = users.create_login_url(self.request.uri)
			is_logged = False

		values = {
			'user': user,
			'url': url,
			'is_logged': is_logged,
		}

		path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
		self.response.out.write(template.render(path, values))

	def put(self):
		pass

class UploadPage(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()

		if user:
			url = users.create_logout_url(self.request.uri)
			self.response.headers['Content-Type'] = 'text/html'
			path = os.path.join(os.path.dirname(__file__), 'templates/upload.html')

			values = {
				'user': user,
				'url': url
			}

			self.response.out.write(template.render(path, values))
		else:
			self.redirect('/')

	def post(self):
		upFile = self.request.get("fbContents")
		if upFile:
			self.response.out.write('Got the file parsing...')
			upFileF = StringIO(upFile)
			zipReader = zipfile.ZipFile(upFileF, 'r')
			self.response.out.write(zipReader.namelist())
			zipReader.close()
			upFileF.close()
		else:
			self.response.out.write('No file')

application = webapp.WSGIApplication(
	[
		('/', MainPage),
		('/upload', UploadPage)
	],
	debug = True
)

def main():
	run_wsgi_app(application)


if __name__ == "__main__":
	main()
