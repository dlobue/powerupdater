#
#   Copyright 2013 Geodelic
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License. 
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#

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

