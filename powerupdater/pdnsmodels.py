
from sqlobject import SQLObject, StringCol, ForeignKey, IntCol, DatabaseIndex
from time import time

CNAME = 'CNAME'
MASTER = 'MASTER'
NS = 'NS'
SOA = 'SOA'


class domain(SQLObject):
    class sqlmeta:
        table = 'domains'

    name = StringCol(length=255, notNone=True)
    master = StringCol(length=128, default=None)
    last_check = IntCol(default=None)
    type = StringCol(length=6, notNone=True)
    notified_serial = IntCol(default=None)
    account = StringCol(length=40, default=None)
    nameIndex = DatabaseIndex(name)

class record(SQLObject):
    class sqlmeta:
        table = 'records'

    domain = ForeignKey('domain', cascade=True)
    name = StringCol(length=255)
    type = StringCol(length=6)
    content = StringCol(length=255)
    ttl = IntCol(default=120)
    prio = IntCol(default=None)
    change_date = IntCol()
    nameIndex = DatabaseIndex(name)
    contentIndex = DatabaseIndex(content)

    def update(self, **kwargs):
        kwargs['change_date'] = int(time())
        return self.set(**kwargs)

    _updated = False
    @classmethod
    def updated(cls, updated=None):
        if updated and not cls._updated:
            cls._updated = True
        return cls._updated

class supermaster(SQLObject):
   class sqlmeta:
       table = 'supermasters'

   ip = StringCol(length=25, notNone=True)
   nameserver = StringCol(length=255, notNone=True)
   account = StringCol(length=40)

