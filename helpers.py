import time
import urllib
import posixpath
import xml.dom.minidom as dom


def check_album_container(c):
	return c.getAttribute('class') == 'album'

def check_photo_container(c):
	return c.getAttribute('class') == 'photo'

def check_comment_container(c):
	return c.getAttribute('class') == 'comment'

def extract_path(link, attribute_name = 'href'):
	return urllib.unquote(link.getAttribute(attribute_name).encode('utf-8'))

def FBdatetime2timestamp(dtime):
	return str(int(time.mktime(time.strptime(dtime, "%B %d, %Y at %I:%M %p" if dtime.endswith('am') or dtime.endswith('pm') else "%B %d, %Y at %H:%M"))) * 1000)

class FBAlbum(object):
	def __init__(self, container):
		links = container.getElementsByTagName('a')
		self.path = extract_path(links[0])
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
	def __init__(self, container):
		#Each link -> [*empty*, photo_path, original_photo_path]
		links = container.getElementsByTagName('a')
		self.path = extract_path(links[1])
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

		self.comments = map(FBComment, filter(check_comment_container, container.getElementsByTagName('div')))


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
