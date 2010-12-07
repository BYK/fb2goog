# coding: utf-8

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import db

import gdata.service
import gdata.alt.appengine
import gdata.photos.service
import gdata.calendar.service
import gdata.docs.client

import os
import sys
import zipfile
from StringIO import StringIO

import models

sys.setrecursionlimit(10000) # SDK fix


class Page(webapp.RequestHandler):
	services = {
		'Picasa': {
			'scope': 'http://picasaweb.google.com/data/',
			'purpose': 'Photos',
			'client': gdata.photos.service.PhotosService
		},
		'Calendar': {
			'scope': 'http://www.google.com/calendar/feeds/',
			'purpose': 'Events',
			'client': gdata.calendar.service.CalendarService
		},
		'Docs': {
			'scope': 'http://docs.google.com/feeds/',
			'purpose': 'Notes',
			'client': gdata.docs.client.DocsClient
		}
	}

	def __init__(self):
		self.user = users.get_current_user()

		if self.user:
			self.url = users.create_logout_url('/')
			self.is_logged = True
		else:
			self.url = users.create_login_url('/services')
			self.is_logged = False

		self.values = {
			'user': self.user,
			'url': self.url,
			'is_logged': self.is_logged,
		}

	def render(self, file, values = None):
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


class ServicesPage(Page):
	def get(self):
		values = self.values.copy()
		values['services'] = []
		for service in self.services:
			values['services'].append({
				'name': service,
				'purpose': self.services[service]['purpose']
			})

		self.render('services.html', values)


	def post(self):
		selected_services = self.request.POST.getall('services')
		user_info = models.User()
		gdata_client = gdata.service.GDataService()
		gdata.alt.appengine.run_on_appengine(gdata_client)

		hostname = os.environ['SERVER_NAME']
		port = os.environ['SERVER_PORT']
		if port and port != '80':
			hostname = hostname + ':' + port
		save_token_url = 'http://' + hostname + '/token'

		scopes = []
		user_info.services = []
		for service in selected_services:
			user_info.services.append(service)
			scopes.append(self.services[service]['scope'])

		if scopes:
			user_info.put()
			self.redirect(gdata_client.GenerateAuthSubURL(save_token_url, scopes, secure = False, session = True).to_string())
		else:
			self.redirect('/services')


class TokenPage(Page):
	def get(self):
		gdata_client = gdata.service.GDataService()
		gdata.alt.appengine.run_on_appengine(gdata_client)

		auth_token = gdata.auth.extract_auth_sub_token_from_url(self.request.uri)
		if not auth_token:
			self.redirect('/services')

		session_token = gdata_client.upgrade_to_session_token(auth_token)
		if not session_token:
			self.redirect('/services')

		gdata_client.token_store.add_token(session_token)
		self.redirect('/upload')

class UploadPage(Page):
	def get(self):
		#if self.user:
		self.render('upload.html')
		#else:
		#	self.redirect('/')

	def post(self):
		archive = self.request.get("fbContents")
		if archive:
			archive_file = StringIO(archive)
			archive_reader = zipfile.ZipFile(archive_file, 'r')

			for name in archive_reader.namelist():
				self.response.out.write("Opening %s...<br>" % name)

				file_content = StringIO(archive_reader.read(name))

				album_url = '/data/feed/api/user/%s/albumid/%s' % (self.user, self.aid)

				photo = self.client.InsertPhotoSimple(
					'/data/feed/api/user/default/albumid/default', 'New Photo',
					'Uploaded using FB2Google', file_content, content_type = 'image/jpeg')

			archive_reader.close()
			archive_file.close()
		else:
			self.response.out.write('No file')


application = webapp.WSGIApplication(
	[
		('/', MainPage),
		('/upload', UploadPage),
		('/services', ServicesPage),
		('/token', TokenPage),
	],
	debug = True
)

def main():
	run_wsgi_app(application)

if __name__ == "__main__":
	main()
