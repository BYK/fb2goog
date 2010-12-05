from google.appengine.ext import db

class User(db.Model):
    username = db.UserProperty(auto_current_user=True, auto_current_user_add=True)
    date = db.DateTimeProperty()
