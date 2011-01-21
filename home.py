# coding: utf-8

import os
import posixpath
import re
import sys
import urllib
import zipfile

from StringIO import StringIO

import gdata.alt.appengine
import gdata.calendar.service
import gdata.docs.client
import gdata.photos.service
import gdata.service

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

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

	def get_user_info(self):
		if self.is_logged:
			return models.User.gql('WHERE name=:1', self.user).get()
		else:
			return None

	def get_user_services(self):
		user_info = self.get_user_info()
		if user_info:
			return user_info.services
		else:
			None

	def get_user_archive(self):
		blob_key = self.get_user_info().blob_key
		archive_blob = blobstore.BlobReader(blob_key)
		return zipfile.ZipFile(archive_blob, 'r') if archive_blob else None #returned file should be manually "closed", might be dangerous

	def render(self, file, values = {}):
		values.update(self.values)
		path = posixpath.join(posixpath.dirname(__file__), 'templates/%s.html' % file)
		self.response.out.write(template.render(path, values))

	def write(self, string):
		self.response.out.write(string)


class MainPage(Page):
	def get(self):
		if self.is_logged:
			#TODO: Create a case block here for proper redirects: upload if blobstore is empty, services if no services activated, process if everything is OK
			#TODO: redirection to upload page should be a separate routine due to special "create_upload_url" system
			upload_url = blobstore.create_upload_url('/upload')
			self.render('upload', {'upload_url': upload_url})
		else:
			self.render('index')


class ServicesPage(Page):
	def get(self):
		values = {'services': []}

		for service in self.services:
			values['services'].append({
				'name': service,
				'purpose': self.services[service]['purpose']
			})

		self.render('services', values)

	def post(self):
		selected_services = self.request.POST.getall('services')

		user_info = self.get_user_info()
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


class UploadPage(blobstore_handlers.BlobstoreUploadHandler, Page):
	def get(self):
		if self.is_logged and self.get_user_services():
			upload_url = blobstore.create_upload_url('/upload')
			self.render('upload', {'upload_url': upload_url})
		else:
			self.redirect('/')

	def post(self):
		data = self.get_uploads('fbContents')
		if self.is_logged and data:
			blob_info = data[0]
			self.redirect('/saved/%s' % blob_info.key())
		else:
			self.redirect('/')


class SavedPage(Page):
	def get(self, blob_key):
		user_info = self.get_user_info()
		user_info.blob_key = str(urllib.unquote(blob_key))
		user_info.put()

		self.render('saved')


class ProcessPage(Page):
	def get(self):
		archive = self.get_user_archive()
		if archive:
			template_values = {}
			archive_files = archive.namelist()

			#TODO: Wrap the functionality below in a class and use it in the Page.services for automatic and flexible service support
			if 'Picasa' in self.get_user_services():
				template_values['Picasa'] = {}
				picasa_client = self.services['Picasa']['client'](email = self.user.email()) #email should be given or InsertAlbum fails
				gdata.alt.appengine.run_on_appengine(picasa_client)

				picasa_albums = picasa_client.GetUserFeed(user = self.user).entry
				albums = get_FB_albums(archive).values()
				for album in albums:
					picasa_album_id = None
					for picasa_album_id in (picasa_album.gphoto_id.text for picasa_album in picasa_albums if picasa_album.title.text == album.title):
						break
					album.picasa_id = picasa_album_id

					#TODO: Prepare template and output variable for visibility and override preferences("albums" already proper?)
					template_values['Picasa']['albums'] = albums
					#self.response.out.write('%s (%s) @ %s %s - on picasa: %s<br>' % (album.title, album.path, album.datetime, album.timestamp, album.picasa_id))

			archive.close()
			self.render('process', template_values)
		else:
			self.redirect('/upload')

	def post(self): #TODO: Create a much better interface for this one. Maybe AJAX?
		archive = self.get_user_archive()
		if archive:
			archive_files = archive.namelist()

			if 'Picasa' in self.get_user_services():
				picasa_client = self.services['Picasa']['client'](email = self.user.email()) #email should be given or InsertAlbum fails
				gdata.alt.appengine.run_on_appengine(picasa_client)

				albums_enabled = self.request.POST.getall('albums_enabled')
				albums = get_FB_albums(archive)
				albums_with_error = []
				for album_title in albums_enabled:
					album = albums[album_title]
					album.picasa_id = self.request.POST.get('album_%s_picasa_id' % (album.title), None)
					self.response.out.write('%s (%s) @ %s %s<br>' % (album.title, album.path, album.datetime, album.timestamp))

					if not album.picasa_id:
						try:
							picasa_album = picasa_client.InsertAlbum(album.title, 'Imported from Facebook via FB2Google', access = self.request.POST.get('album_%s_visibility' % (album.title), 'private'), timestamp = album.timestamp)
							album.picasa_id = picasa_album.gphoto_id.text
						except: # SomeError as Something?
							albums_with_error.append(album_title) #or a dict with error details? may be including failed photos list?
							continue

					picasa_album_url = '/data/feed/api/user/default/albumid/%s' % album.picasa_id

					photos = get_FB_album_photos(archive, album)
					for photo in photos:
						self.response.out.write('%s (%s) @ %s<br>Tags: %s<br>' % (photo.caption, photo.path, photo.datetime, ', '.join(photo.tags)))
						for comment in photo.comments:
							self.response.out.write('%s: %s @ %s<br>' % (comment.author, comment.message, comment.datetime))

						photo_content = StringIO(archive.read(photo.path))
						#TODO: put image upload code into a try-catch block to handle possible errors
						try:
							picasa_photo = picasa_client.InsertPhotoSimple(picasa_album_url, photo.caption, 'Imported from Facebook via FB2Google, original creation date: %s' % photo.datetime, photo_content, 'image/jpeg', photo.tags)
						except: # SomeError as Something?
							#TODO: Log the failed photo somewhere.
							self.response.out.write('<br><strong>Failed!</strong><br>')
							continue

			else:
				self.write('No permission for Picasa.')

			archive.close()
		else:
			self.redirect('/upload')


application = webapp.WSGIApplication(
	[
		('/', MainPage),
		('/upload', UploadPage),
		('/process', ProcessPage),
		('/services', ServicesPage),
		('/token', TokenPage),
		('/saved/([^/]+)?', SavedPage),
	],
	debug = True
)

def main():
	run_wsgi_app(application)

if __name__ == "__main__":
	main()
