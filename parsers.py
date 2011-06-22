import time
import urllib
import posixpath
import xml.dom.minidom as dom


def extract_path(link, attribute_name = 'href'):
	return urllib.unquote(link.getAttribute(attribute_name).encode('utf-8'))

def FBdatetime2timestamp(dtime):
	try: #try to parse using standart US date format
		return str(int(time.mktime(time.strptime(dtime, "%B %d, %Y at %I:%M %p" if dtime.endswith('am') or dtime.endswith('pm') else "%B %d, %Y at %H:%M"))) * 1000)
	except: #return None if parsing fails
		return None

def get_FB_albums(archive_reader):
	for photos_page_name in (name for name in archive_reader.namelist() if name.endswith('photos.html')):
		break #Get the first entry in the file list ending with "photos.html"
	album_root_path = posixpath.dirname(photos_page_name) + '/'
	photos_page = dom.parseString(archive_reader.read(photos_page_name).replace('<BR>', '<br/>'))
	albums = {}
	for container in photos_page.getElementsByTagName('div'):
		if container.getAttribute('class') == 'album':
			parsedAlbum = FBAlbum(container, album_root_path)
			albums[parsedAlbum.title] = parsedAlbum
	return albums

def get_FB_album_photos(archive_reader, album):
	photo_root_path = posixpath.dirname(album.path) + '/'
	album_page = dom.parseString(archive_reader.read(album.path).replace('<BR>', '<br/>'))
	photos = []
	for container in album_page.getElementsByTagName('div'):
		if container.getAttribute('class') == 'photo':
			photos.append(FBPhoto(container, photo_root_path))
	return photos

class FBAlbum(object):
	def __init__(self, container, root_path = ""):
		links = container.getElementsByTagName('a')
		self.path = posixpath.normpath(root_path + urllib.unquote(extract_path(links[0])))
		self.title = unicode(links[1].firstChild.nodeValue)
		self.cover_photo_path = extract_path(container.getElementsByTagName('img')[0], 'src')

		for elem in container.childNodes:
			if elem.nodeType != dom.Node.TEXT_NODE and elem.tagName == 'span' and elem.getAttribute('class') == 'time':
				self.datetime = elem.firstChild.nodeValue
				self.timestamp = FBdatetime2timestamp(self.datetime)
				break
			else:
				self.datetime = None
				self.timestamp = None

class FBPhoto(object):
	def __init__(self, container, root_path = ""):
		#Each link -> [*empty*, photo_path, original_photo_path]
		links = container.getElementsByTagName('a')
		self.path = posixpath.normpath(root_path + extract_path(links[1]))
		self.datetime = links[2].getElementsByTagName('span')[0].firstChild.nodeValue
		self.timestamp = FBdatetime2timestamp(self.datetime)

		line_breaks = container.getElementsByTagName('br')
		self.caption = line_breaks[0].nextSibling.nodeValue.strip()
		if self.caption == 'In this video:':
			self.caption = ''

		if self.caption == '':
			self.caption = posixpath.splitext(posixpath.basename(self.path))[0]

		self.tags = []
		for br in line_breaks:
			if br.nextSibling.nodeValue and br.nextSibling.nodeValue.strip() == 'In this video:':
				span_element = br.nextSibling.nextSibling
				next_br = line_breaks[line_breaks.index(br) + 1]

				while span_element != next_br:
					if span_element.nodeType != dom.Node.TEXT_NODE and span_element.tagName == 'span':
						self.tags.append(span_element.firstChild.nodeValue)
					span_element = span_element.nextSibling

				break

		self.comments = map(FBComment, (comment_container for comment_container in container.getElementsByTagName('div') if comment_container.getAttribute('class') == 'comment'))


class FBComment(object):
	def __init__(self, container):
		self.author = container.firstChild.firstChild.nodeValue
		self.datetime = container.lastChild.firstChild.nodeValue
		self.timestamp = self.timestamp = FBdatetime2timestamp(self.datetime)
		self.message = ''
		node = container.childNodes[1]
		while node != container.lastChild:
			if node.nodeType == dom.Node.TEXT_NODE:
				self.message += node.nodeValue
			elif node.nodeType == dom.Node.ELEMENT_NODE and node.tagName.lower() == 'br':
				self.message += "\n"

			node = node.nextSibling
