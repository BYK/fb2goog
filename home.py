# coding: utf-8

import os
import sys
import zipfile

import gdata.alt.appengine
import gdata.service

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import webapp
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import models

from importers import *

sys.setrecursionlimit(10000)  # SDK fix


class Page(webapp.RequestHandler):
    services = {
        'Picasa': {
            'scope': 'http://picasaweb.google.com/data/',
            'purpose': 'Photos',
            'settings': PicasaSettingsProvider,
            'importer': PicasaImporter
        },
        'Calendar': {
            'scope': 'http://www.google.com/calendar/feeds/',
            'purpose': 'Events',
            #'client': gdata.calendar.service.CalendarService
        },
        'Docs': {
            'scope': 'http://docs.google.com/feeds/',
            'purpose': 'Notes',
            #'client': gdata.docs.client.DocsClient
        }
    }

    def __init__(self):
        super(Page, self).__init__()

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

    def get_user_archive(self):
        user_info = self.get_user_info()
        if not user_info:
            return None

        blob_key = user_info.blob_key
        archive_blob = blobstore.BlobReader(blob_key)

        # returned file should be manually "closed", might be dangerous
        return zipfile.ZipFile(archive_blob, 'r') if archive_blob else None

    def render(self, file_name, values=None):
        if values is None:
            values = {}

        values.update(self.values)
        path = posixpath.join(posixpath.dirname(__file__),
                              'templates/%s.html' % file_name)
        self.response.out.write(template.render(path, values))

    def write(self, string):
        self.response.out.write(string)


class MainPage(Page):
    def get(self):
        if self.is_logged:
            # TODO: Create a case block here for proper redirects: upload if
            #       blob store is empty, services if no services activated,
            #       process if everything is OK
            # TODO: redirection to upload page should be a separate routine due
            #       to special "create_upload_url" system

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
            self.redirect(gdata_client.GenerateAuthSubURL(
                save_token_url, scopes, secure=False, session=True).to_string()
            )
        else:
            self.redirect('/services')


class TokenPage(Page):
    def get(self):
        gdata_client = gdata.service.GDataService()
        gdata.alt.appengine.run_on_appengine(gdata_client)

        token = gdata.auth.extract_auth_sub_token_from_url(self.request.uri)
        if not token:
            self.redirect('/services')

        session_token = gdata_client.upgrade_to_session_token(token)
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
            user_info = self.get_user_info()
            if user_info.blob_key:
                blobstore.delete(user_info.blob_key)
            user_info.blob_key = str(blob_info.key())
            user_info.put()
            self.redirect('/saved')
        else:
            self.redirect('/')


class SavedPage(Page):  # Unnecessary?
    def get(self):
        self.render('saved')


class ProcessPage(Page):
    def get(self):
        archive = self.get_user_archive()
        if archive:
            template_values = {}

            for service in self.get_user_services():
                settings_provider = self.services[service]['settings'](
                    self.user, archive
                )
                template_values[service] = settings_provider.template_vars

            archive.close()
            self.render('process', template_values)

    def post(self):  # TODO: Separate this part for "task" section
        logging.info('Import request received for user %s', self.user)
        archive = self.get_user_archive()
        if archive:
            for service in self.get_user_services():
                self.response.out.write('Importing to service %s...' % service)
                importer = self.services[service]['importer'](
                    self.user, archive, self.request.POST
                )
                import_result = importer.do_import()
                if import_result == 0:
                    self.response.out.write(
                        '%s import completed successfully.' % service
                    )
                else:
                    self.response.out.write(
                        '%s import completed with errors. (code %d)' %
                        (service, import_result)
                    )

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
        ('/saved', SavedPage),
    ],
    debug=True
)


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
