# coding: utf-8

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import db

import gdata.service
import gdata.alt.appengine
import gdata.photos.service
import gdata.media
import gdata.geo

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
			self.url = users.create_login_url('/welcome')
			self.is_logged = False

		next = 'http://localhost:8080/'
		self.scope = ('http://picasaweb.google.com/data/',)

		self.aid = '533644030096334264'

		self.client = gdata.photos.service.PhotosService()
		gdata.alt.appengine.run_on_appengine(self.client)

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
		"""albums = self.client.GetUserFeed(user=self.user)
		for album in albums.entry:
			self.response.out.write('title: %s, number of photos: %s, id: %s' % (album.title.text,
				album.numphotos.text, album.gphoto_id.text))"""
		

		if self.is_logged:
			self.render('upload.html')
		else:
			self.render('index.html')



class WelcomePage(Page):
	def get(self):
		token_request_url = None

		auth_token = gdata.auth.extract_auth_sub_token_from_url(self.request.uri)

		if auth_token:
			self.client.SetAuthSubToken(self.client.upgrade_to_session_token(auth_token))

		#if not isinstance(self.client.token_store.find_token('http://picasaweb.google.com/data/'), gdata.auth.AuthSubToken):
		token_request_url = gdata.auth.generate_auth_sub_url(self.request.uri, self.scope)

		self.response.out.write('<a href="%s">Access</a>' % token_request_url)

		



class UploadPage(Page):
	def get(self):
		#if self.user:
		self.render('upload.html')
		#else:
		#	self.redirect('/')


	def post(self):
		upFile = self.request.get("fbContents")
		if upFile:
			upFileF = StringIO(upFile)

			zipReader = zipfile.ZipFile(upFileF, 'r')
			
			#self.response.out.write(zipReader.namelist())

			for i, name in enumerate(zipReader.namelist()):
				self.response.out.write("Opening %s...<br>" % name)
				
				filename = StringIO(zipReader.read(name))

				album_url = '/data/feed/api/user/%s/albumid/%s' % (self.user, self.aid)
				#photo = self.client.InsertPhotoSimple(album_url, 'New Photo', 'Uploaded using the API', filename, content_type='image/jpeg')
				photo = self.client.InsertPhotoSimple(
    '/data/feed/api/user/default/albumid/default', 'New Photo', 
    'Uploaded using the API', filename, content_type='image/jpeg')
				#self.response.out.write(filename)
			
			zipReader.close()
			upFileF.close()
		else:
			self.response.out.write('No file')



application = webapp.WSGIApplication(
	[
		('/', MainPage),
		('/upload', UploadPage),
		('/welcome', WelcomePage),
	],
	debug = True
)

def main():
	run_wsgi_app(application)


if __name__ == "__main__":
	main()
