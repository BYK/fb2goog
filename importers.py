import logging

from StringIO import StringIO

import gdata.alt.appengine
import gdata.calendar.service
import gdata.docs.client
import gdata.photos.service
import gdata.service

from parsers import *

class PicasaImporter(object):
	def __init__(self, user, archive, preferences):
		self.user = user
		self.archive = archive
		self.preferences = preferences

		logging.debug('Getting Picasa client for user %s', self.user)
		self.client = gdata.photos.service.PhotosService(email = self.user.email()) #email should be given or InsertAlbum fails
		gdata.alt.appengine.run_on_appengine(self.client)
		logging.debug('Picasa client for user %s initialized.', self.user)

		albums_parsed = get_FB_albums(archive)
		logging.info('Parsed %d albums for user %s.', albums_parsed.__len__(), self.user)
		albums_enabled = preferences.getall('albums_enabled')
		self.albums = (albums_parsed[title] for title in albums_enabled)

	def do_import(self):
		status = 0
		for album in self.albums:
			album.picasa_id = self.preferences.get('album_%s_picasa_id' % (album.title), None)
			#self.response.out.write('%s (%s) @ %s %s<br>' % (album.title, album.path, album.datetime, album.timestamp))

			if not album.picasa_id:
				logging.debug('Creating album %s in Picasa...', album.title)
				visibility = self.preferences.get('album_%s_visibility' % (album.title), 'private')
				picasa_album = self.client.InsertAlbum(album.title, 'Imported from Facebook via FB2Google', access = visibility, timestamp = album.timestamp)
				album.picasa_id = picasa_album.gphoto_id.text
				logging.debug('Album %s is created in Picasa with visibility level "%s". Picasa Id: %s', album.title, visibility, album.picasa_id)

			picasa_album_url = '/data/feed/api/user/default/albumid/%s' % album.picasa_id

			photos = get_FB_album_photos(self.archive, album)
			logging.debug('Parsed %d photos in album %s. Importing to Picasa...', photos.__len__(), album.title)
			for photo in photos:
				#self.response.out.write('%s (%s) @ %s<br>Tags: %s<br>' % (photo.caption, photo.path, photo.datetime, ', '.join(photo.tags)))
				#for comment in photo.comments:
				#	self.response.out.write('%s: %s @ %s<br>' % (comment.author, comment.message, comment.datetime))

				photo_content = StringIO(self.archive.read(photo.path))
				try:
					picasa_photo = self.client.InsertPhotoSimple(picasa_album_url, photo.caption, 'Imported from Facebook via FB2Google, original creation date: %s' % photo.datetime, photo_content, 'image/jpeg', photo.tags)
				except GooglePhotosException:
					status = 1
					logging.exception('Uploading of a photo failed. (User: %s, Album: %s, Photo: %s)', self.user, album.title, photo.caption)
					continue
			logging.debug('Importing of album %s completed.', album.title)
			return status

