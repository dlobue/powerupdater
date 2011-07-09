
from time import time
from ConfigParser import SafeConfigParser
from functools import wraps
from sys import argv
import logging
logger = logging.getLogger(__name__)

from sqlobject import connectionForURI, sqlhub, SQLObjectNotFound, AND
from sqlobject.main import SQLObjectIntegrityError
import boto
import boto.ec2

from pdnsmodels import record, domain, CNAME, MASTER, SOA


def memoize(fctn):
    memory = {}
    @wraps(fctn)
    def memo(*args):
        haxh = tuple(args)

        if haxh not in memory:
            memory[haxh] = fctn(*args)

        return memory[haxh]
    return memo


try:
    dnsdb = argv[1]
except IndexError:
    dnsdb = '/var/spool/powerdns/pdns.sqlite'
conn_str = 'sqlite://%s' % dnsdb
connection = connectionForURI(conn_str)
sqlhub.processConnection = connection


def trampoline(*instance_lists):
    instance_lists = iter(instance_lists)
    while 1:
        instances = iter(instance_lists.next())
        while 1:
            try:
                yield instances.next()
            except StopIteration:
                break



@memoize
def get_rootdn_record(name):
    try:
        return domain.selectBy(name=name).getOne()
    except SQLObjectNotFound:
        return domain(name=name, type=MASTER)


def gatherinstances():
    regions = (region.connect() for region in boto.ec2.regions())
    instances = (region.get_all_instances() for region in regions)

    return trampoline(*instances)


def process_all(instances):
    started_at = int(time())

    instances = map(lambda x: x.instances[0], instances)
    instances = filter(lambda x: x.tags, instances)

    def _process(fqdn, domain_base, public_dns_name):
        try:
            sr = record.selectBy(name=fqdn).getOne()
            if sr.content != public_dns_name:
                sr.update(content=public_dns_name)
            else:
                return sr #record already existed, and didn't get updated, so
                          # change_date will still be older than started_at.
                          # return it for exclusion in stale record processing.
        except SQLObjectNotFound:
            sr = record(domain=get_rootdn_record(domain_base),
                        name=fqdn, type=CNAME,
                        content=public_dns_name, change_date=int(time()))


    no_changes = filter(lambda x: x,
                        map(lambda x: _process(x.tags['fqdn'],
                                               x.tags['domain_base'],
                                               x.dns_name), instances))

    arrays = filter(lambda x: x.tags['fqdn'].startswith('array-'), instances)
    array_types = {}

    for array_instance in arrays:
        fqdn_parts = array_instance.tags['fqdn'].split('.')
        array_type = fqdn_parts.pop(0)[:-3]
        deployment = array_instance.tags['deployment']
        array_type = array_type.replace('array-','')
        fqdn_parts.insert(0, '%sXX' % array_type)
        fqdn = '.'.join(fqdn_parts)
        atypedeploy = array_types.setdefault(deployment, {})
        atypes = atypedeploy.setdefault(array_type, [])
        atypes.append((fqdn, array_instance))

    for deploy,atypesdict in array_types.iteritems():
        for atype,v in atypesdict.iteritems():
            for e,(fqdn,array_instance) in enumerate(v):
                e += 1
                e = str(e).zfill(2)
                fqdn = fqdn.replace('XX', e)
                result = _process(fqdn, array_instance.tags['domain_base'],
                         array_instance.dns_name)
                if result:
                    no_changes.append(result)



    not_updated = record.select(AND(record.q.change_date<started_at, record.q.type == CNAME))

    for rcrd in not_updated:
        if rcrd not in no_changes:
            rcrd.destroySelf()

    if record.updated():
        #TODO: account for multiple domain bases
        try:
            soa = record.selectBy(type=SOA).getOne()
        except SQLObjectNotFound:
            logger.debug("No SOA record found")
            return None
        except SQLObjectIntegrityError:
            logger.warn("Found more than one SOA record.")
            return None

        soa_contents = soa.content.split()
        if len(soa_contents) < 2:
            logger.error("Incomplete SOA record: %s" % soa.content)
            return None

        try:
            serial = int(soa_contents[2]) + 1
        except IndexError:
            serial = 1
        except ValueError:
            logger.error("Invalid value for SOA record serial number! Got: %r" % soa_contents[2])
            return None

        try:
            soa_contents[2] = str(serial)
        except IndexError:
            soa_contents.append( str(serial) )
        soa.update(content=' '.join(soa_contents))



def created_listener(inst, kwargs, post_funcs):
    inst.updated(True)
    logger.info("New server found - fqdn: %s" % inst.name)

def updated_listener(inst, post_funcs):
    inst.updated(True)
    logger.info("Updating %s record for server - fqdn: %s" % (inst.type, inst.name))

def destroy_listener(inst, post_funcs):
    inst.updated(True)
    logger.info("Deleting record for server - fqdn: %s" % inst.name)


def do_update():
    from sqlobject.events import listen, RowDestroySignal, RowCreatedSignal, RowUpdatedSignal
    listen(created_listener, record, RowCreatedSignal)
    listen(updated_listener, record, RowUpdatedSignal)
    listen(destroy_listener, record, RowDestroySignal)
    process_all(gatherinstances())




if __name__ == '__main__':
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    do_update()

