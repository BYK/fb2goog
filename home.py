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

import models

sys.setrecursionlimit(10000) # SDK fix


class Page(webapp.RequestHandler):
	def __init__(self):
		self.user = users.get_current_user()

		if self.user:
			self.url = users.create_logout_url('/')
			self.is_logged = True
		else:
			self.url = users.create_login_url('/')
			self.is_logged = False

		self.values = {
			'user': self.user,
			'url': self.url,
			'is_logged': self.is_logged,
		}


	def render(self, file, values=None):
		self.response.headers['Content-Type'] = 'text/html'

		path = os.path.join(os.path.dirname(__file__), 'templates/%s' % file)

		self.response.out.write(template.render(path, values if values else self.values))



class MainPage(Page):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'

		if self.is_logged:
			self.render('upload.html')
		else:
			self.render('index.html')



class UploadPage(Page):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
			
		if self.user:
			self.render('upload.html')
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
		('/upload', UploadPage),
	],
	debug = True
)

def main():
	run_wsgi_app(application)


if __name__ == "__main__":
	main()
