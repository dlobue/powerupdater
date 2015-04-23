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

from functools import wraps
from pprint import pformat
from collections import Iterable
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


def trampoline(*list_of_lists):
    stack = [list_of_lists]
    iteree = iter(stack)
    while 1:
        try:
            item = iteree.next()
        except StopIteration:
            try:
                iteree = iter(stack.pop())
                continue
            except IndexError:
                break

        if isinstance(item, Iterable) and not isinstance(item, basestring):
            stack.append(iteree)
            iteree = iter(item)
            continue
        yield item




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

    zid = zone['Id'].replace('/hostedzone/', '')
    results = rrsets = route53.get_all_rrsets(zid)

    while rrsets.is_truncated:
        rrsets = route53.get_all_rrsets(zid, name=rrsets.next_record_name, type=rrsets.next_record_type)
        results.extend(rrsets)

    return results


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
    reservations = (region.get_all_instances() for region in regions)
    instances = (reservation.instances for reservation in trampoline(reservations))

    return trampoline(instances)


def process_all(instances):
    instances = filter(lambda x: x.tags and x.dns_name and all((y in x.tags for y in ('domain_base', 'fqdn', 'deployment'))), instances)

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
        deployment = array_instance.tags['deployment']

        fqdn = array_instance.tags['fqdn']
        fqdn_base = fqdn[fqdn.index('.'):]

        if 'type' in array_instance.tags:
            array_type = array_instance.tags['type']
        else:
            array_type = fqdn[:fqdn.index('.')][:-3]
            array_type = array_type.replace('array-','')

        fqdn_alias = array_type + 'XX' + fqdn_base

        atypedeploy = array_types.setdefault(deployment, {})
        atypes = atypedeploy.setdefault(array_type, [])
        atypes.append((fqdn_alias, array_instance))

    for deploy,atypesdict in array_types.iteritems():
        for atype,v in atypesdict.iteritems():
            v = sorted(v, key=lambda x: x[1].launch_time)
            for e,(fqdn_alias,array_instance) in enumerate(v):
                e = str(e+1).zfill(2)
                fqdn = fqdn_alias.replace('XX', e)

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

