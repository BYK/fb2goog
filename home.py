# coding: utf-8

import os
import posixpath
import re
import sys
import xml.dom.minidom as minidom
import zipfile

from StringIO import StringIO

import gdata.alt.appengine
import gdata.calendar.service
import gdata.docs.client
import gdata.photos.service
import gdata.service

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import models

from helpers import *


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
			'is_logged': self.is_logged
		}


	def check_user_services(self):
		return models.User.gql('WHERE name = :1', self.user).get().services


	def render(self, file, values = None):
		self.response.headers['Content-Type'] = 'text/html'

		path = posixpath.join(posixpath.dirname(__file__), 'templates/%s.html' % file)
		self.response.out.write(template.render(path, values if values else self.values))



class MainPage(Page):
	def get(self):
		if self.is_logged:
			self.render('upload')
		else:
			self.render('index')



class ServicesPage(Page):
	def get(self):
		values = self.values.copy()
		values['services'] = []

		for service in self.services:
			values['services'].append({
				'name': service,
				'purpose': self.services[service]['purpose']
			})

		self.render('services', values)


	def post(self):
		selected_services = self.request.POST.getall('services')

		user_info = models.User.gql('WHERE name=:1', self.user).get()
		if not user_info:
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
		if self.is_logged and self.check_user_services():
			self.render('upload')
		else:
			self.redirect('/')


	def post(self):
		archive = self.request.get("fbContents")
		if archive:
			archive_file = StringIO(archive)
			archive_reader = zipfile.ZipFile(archive_file, 'r')
			archive_files = archive_reader.namelist()

			#TODO: Do not activate photo import if the user did not selected Picasa from services
			picasa_client = self.services['Picasa']['client'](email = self.user.email()) #email should be given or InsertAlbum fails
			gdata.alt.appengine.run_on_appengine(picasa_client)

			#TODO: Should check if an album with the same name exists and ask wheter to replace it, add into it or create a new one
			#user_albums = picasa_client.GetUserFeed(user = self.user).entry
			#for album in user_albums:
			#	self.response.out.write('title: %s, number of photos: %s, id: %s' % (album.title.text, album.numphotos.text, album.gphoto_id))

			photos_page_name = filter(lambda x: x.endswith('photos.html'), archive_files)[0]
			album_root_path = posixpath.dirname(photos_page_name) + '/'
			photos_page = minidom.parseString(archive_reader.read(photos_page_name).replace('<BR>', '<br/>'))

			self.response.out.write(photos_page.getElementsByTagName('div'))

			albums = map(FBAlbum, filter(check_album_container, photos_page.getElementsByTagName('div')))
			for album in albums:
				album.path = posixpath.normpath(album_root_path + urlparse.unquote(album.path))
				self.response.out.write('%s (%s) @ %s<br>' % (album.title,
				album.path,
				album.datetime))

				#TODO: Ask user album visibility preference
				picasa_album = picasa_client.InsertAlbum(album.title, 'Imported from Facebook via FB2Google', access = "private", timestamp = album.timestamp)
				picasa_album_url = '/data/feed/api/user/default/albumid/%s' % picasa_album.gphoto_id.text

				photo_root_path = posixpath.dirname(album.path) + '/'
				album_page = minidom.parseString(archive_reader.read(album.path).replace('<BR>', '<br/>'))
				photos = map(FBPhoto, filter(check_photo_container, album_page.getElementsByTagName('div')))
				for photo in photos:
					photo.path = posixpath.normpath(photo_root_path + photo.path)
					self.response.out.write('%s (%s) @ %s<br>Tags: %s<br>' % (photo.caption, photo.path, photo.datetime, ', '.join(photo.tags)))
					for comment in photo.comments:
						self.response.out.write('%s: %s @ %s<br>' % (comment.author, comment.message, comment.datetime))

					photo_content = StringIO(archive_reader.read(photo.path))
					#picasa_photo = picasa_client.InsertPhotoSimple(picasa_album_url, photo.caption, 'Imported from Facebook via FB2Google, original creation date: %s' % photo.datetime, photo_content, 'image/jpeg', photo.tags)

				self.response.out.write('<br>')
				break

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
