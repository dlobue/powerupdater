
from functools import wraps
from pprint import pformat
import logging
logger = logging.getLogger(__name__)

import boto
import boto.ec2


DEFAULT_TTL = 120
DEFAULT_TYPE = 'CNAME'


route53 = boto.connect_route53()


def memoize(fctn):
    memory = {}
    @wraps(fctn)
    def memo(*args):
        haxh = tuple(args)

        if haxh not in memory:
            memory[haxh] = fctn(*args)

        return memory[haxh]
    return memo


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
def get_records(name):
    zones = route53.get_all_hosted_zones()['ListHostedZonesResponse']['HostedZones']
    name = name.strip('.')
    zones = filter(lambda x: x['Name'].strip('.') == name, zones)
    if zones:
        zone = zones[0]
    else:
        response = route53.create_hosted_zone(name)
        zone = response['CreateHostedZoneResponse']['HostedZone']
    return route53.get_all_rrsets(zone['Id'].replace('/hostedzone/', ''))


def delete_record(rrset, record):
    c = rrset.add_change('DELETE', record.name, record.type, record.ttl)
    for v in record.resource_records:
        c.add_value(v)
    return rrset

def find_record(rrset, name):
    name = name.strip('.')
    return filter(lambda x: x.name.strip('.') == name, rrset)[0]

def process_record(rrset, name, value):
    name = name.strip('.')
    try:
        record = find_record(rrset, name)
    except IndexError:
        logger.info("New: %s" % name)
        pass
    else:
        if record.resource_records[0] == value:
            logger.debug("Unchanged: %s" % name)
            return rrset

        logger.info("Updating: %s" % name)
        logger.debug("Name: %s, Old values: %r, New value: %r" % (name, record.resource_records, value))
        rrset = delete_record(rrset, record)

    c = rrset.add_change('CREATE', name, 'CNAME', DEFAULT_TTL)
    c.add_value(value)

    return rrset

def gatherinstances():
    regions = (region.connect() for region in boto.ec2.regions())
    instances = (region.get_all_instances() for region in regions)

    return trampoline(*instances)


def process_all(instances):
    instances = map(lambda x: x.instances[0], instances)
    instances = filter(lambda x: x.tags and x.dns_name, instances)

    domain_bases = set(x.tags['domain_base'] for x in instances)

    unseen = {}
    for d in domain_bases:
        unseen[d] = set(r.name.strip('.') for r in get_records(d) if r.type == 'CNAME')


    for instance in instances:
        unseen[instance.tags['domain_base']].discard(instance.tags['fqdn'])
        rrset = get_records(instance.tags['domain_base'])
        process_record(rrset, instance.tags['fqdn'], instance.dns_name)


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
                e = str(e+1).zfill(2)
                fqdn = fqdn.replace('XX', e)

                unseen[array_instance.tags['domain_base']].discard(fqdn)
                rrset = get_records(array_instance.tags['domain_base'])
                process_record(rrset, fqdn, array_instance.dns_name)



    for d,records in unseen.iteritems():
        rrset = get_records(d)
        for rname in records:
            logger.info("Deleting: %s" % rname)
            record = find_record(rrset, rname)
            delete_record(rrset, record)

    for d in domain_bases:
        rrset = get_records(d)
        if rrset.changes:
            logger.info("committing changes for domain base: %s" % d)
            logger.debug(pformat(rrset.changes))
            rrset.commit()



def do_update():
    process_all(gatherinstances())


if __name__ == '__main__':
    from time import time
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    t = time()
    do_update()
    print('took %f seconds to run' % (time() - t))

