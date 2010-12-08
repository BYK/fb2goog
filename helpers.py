import urlparse
import xml.dom.minidom as minidom

def check_album_container(c):
	return c.getAttribute('class') == 'album'

def check_photo_container(c):
	return c.getAttribute('class') == 'photo'

def extract_path(link, attribute_name = 'href'):
	return urlparse.unquote(link.getAttribute(attribute_name).encode('utf-8'))

class FBAlbum(object):
	def __init__(self, container):
		links = container.getElementsByTagName('a')
		self.path = extract_path(links[0])
		self.title = links[1].firstChild.nodeValue
		self.cover_photo_path = extract_path(container.getElementsByTagName('img')[0], 'src')

		for elem in container.childNodes:
			if elem.nodeType != minidom.Node.TEXT_NODE and elem.tagName == 'span' and elem.getAttribute('class') == 'time':
				self.timestamp = elem.firstChild.nodeValue
				break


class FBPhoto(object):
	def __init__(self, container):
		#Each link -> [*empty*, photo_path, original_photo_path]
		links = container.getElementsByTagName('a')
		self.path = extract_path(links[1])
		self.timestamp = links[2].getElementsByTagName('span')[0].firstChild.nodeValue

		line_breaks = container.getElementsByTagName('br')
		self.caption = line_breaks[0].nextSibling.nodeValue.strip()
		if self.caption == 'In this video:':
			self.caption = ''

		self.tags = []

		for br in line_breaks:
			if br.nextSibling.nodeValue and br.nextSibling.nodeValue.strip() == 'In this video:':
				span_element = br.nextSibling.nextSibling
				next_br = line_breaks[line_breaks.index(br) + 1]

				while span_element != next_br:
					if span_element.nodeType != minidom.Node.TEXT_NODE and span_element.tagName == 'span':
						self.tags.append(span_element.firstChild.nodeValue)
					span_element = span_element.nextSibling

				break
