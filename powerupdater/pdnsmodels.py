
from sqlobject import SQLObject, StringCol, ForeignKey, IntCol, DatabaseIndex
from time import time

CNAME = 'CNAME'
MASTER = 'MASTER'


class domain(SQLObject):
    class sqlmeta:
        table = 'domains'
        #lazyUpdate = True

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
        #lazyUpdate = True

    domain = ForeignKey('domain', cascade=True)
    name = StringCol(length=255)
    type = StringCol(length=6)
    content = StringCol(length=255)
    ttl = IntCol(default=600)
    prio = IntCol(default=None)
    change_date = IntCol()
    nameIndex = DatabaseIndex(name)
    contentIndex = DatabaseIndex(content)

    def update(self, **kwargs):
        kwargs['change_date'] = int(time())
        return self.set(**kwargs)

#class supermaster(SQLObject):
    #    class sqlmeta:
        #        table = 'supermasters'

#    ip = StringCol(length=25, notNone=True)
#    nameserver = StringCol(length=255, notNone=True)
#    account = StringCol(length=40)

