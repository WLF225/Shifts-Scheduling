# Django's MySQL backend expects the MySQLdb driver. PyMySQL is what the
# SQLAlchemy engine already uses, so register it under that name rather than
# adding a second driver. Must run before django.db loads.
import pymysql

pymysql.install_as_MySQLdb()
