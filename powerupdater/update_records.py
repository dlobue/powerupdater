
from time import time

from sqlobject import connectionForURI, sqlhub, SQLObjectNotFound
import boto
import boto.ec2
from ConfigParser import SafeConfigParser
from os.path import expanduser

from pdnsmodels import record, domain, CNAME, MASTER
from functools import wraps


def memoize(fctn):
    memory = {}
    @wraps(fctn)
    def memo(*args):
        haxh = tuple(args)

        if haxh not in memory:
            memory[haxh] = fctn(*args)

        return memory[haxh]
    return memo


#dnsdb = '/root/pdns.sqlite'
dnsdb = '/var/spool/powerdns/pdns.sqlite'
conn_str = 'sqlite://%s' % dnsdb
connection = connectionForURI(conn_str)
sqlhub.processConnection = connection

def get_credentials():
    confp = SafeConfigParser()
    confp.read(expanduser('~/.s3cfg'))
    return {'aws_access_key_id': confp.get('default', 'access_key'),
            'aws_secret_access_key': confp.get('default', 'secret_key')}


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
    regions = boto.ec2.regions(**get_credentials())
    regions = (region.connect(**get_credentials()) for region in regions)

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



    not_updated = record.select(record.q.change_date<started_at)

    for rcrd in not_updated:
        if rcrd not in no_changes:
            rcrd.destroySelf()



def created_listener(inst, kwargs, post_funcs):
    print("New server found - fqdn: %s" % inst.name)

def destroy_listener(inst, post_funcs):
    print("Deleting record for server - fqdn: %s" % inst.name)


def do_update():
    #from sqlobject.events import listen, RowDestroySignal, RowCreatedSignal
    #listen(created_listener, record, RowCreatedSignal)
    #listen(destroy_listener, record, RowDestroySignal)
    process_all(gatherinstances())




if __name__ == '__main__':
    do_update()

