
from pprint import pformat
import logging
logger = logging.getLogger(__name__)

import dns.resolver
import dns.name

trusted_resolvers = ['4.2.2.2', '4.2.2.3', '4.2.2.4']


def walk_dns(target):
    stack = []
    while 1:
        stack.append(target)
        try:
            target = target.parent()
            if not target[0]:
                return stack
        except dns.name.NoParent:
            return stack


def get_addresses(target, trusted_resolver):
    result = set()
    stash = []
    current = iter([target])
    while 1:
        try:
            record = current.next()
        except StopIteration:
            try:
                current = stash.pop()
            except IndexError:
                logger.debug('get_address using %s generated %s' %
                             (target, pformat(result)))
                return result

        if hasattr(record, 'target'):
            record = record.target

        try:
            result.add(record.address)
        except AttributeError:
            stash.append(current)
            if isinstance(record, dns.name.Name):
                logger.debug("using trusted ns servers to resolve %s" % record)
                record = trusted_resolver.query(record, 'A')
            elif isinstance(record, dns.resolver.Answer):
                if record.rrset is None:
                    record = record.response.authority
            current = iter(record)


def find_ns(target):
    target = dns.name.from_text(target)
    stack = walk_dns(target)
    #stack = []
    #stack.append(target)
    #stack.append(target.parent())
    logger.debug('starting stack: %s' % pformat(stack))

    trusted_resolver = dns.resolver.Resolver()
    trusted_resolver.nameservers = trusted_resolvers
    walking_resolver = dns.resolver.Resolver()
    walking_resolver.nameservers = trusted_resolvers
    level_nameservers = trusted_resolvers
    level_ns_names = []

    while 1:
        try:
            level = stack.pop()
            logger.debug('resolv level at %r' % level)
        except IndexError:
            logger.debug('last nameservers:\n%s' % pformat(level_nameservers))
            logger.debug('last nameserver names:\n%s' % pformat(level_ns_names))
            break
        try:
            level_ns_names = walking_resolver.query(level, 'NS', raise_on_no_answer=False)
        except dns.resolver.NoAnswer:
            logger.warn("failing over to trusted resolver - walking resolver failed querying %s using the nameservers: %s" %
                        (level.to_text(), pformat(walking_resolver.nameservers)))
            level_ns_names = trusted_resolver.query(level, 'NS', raise_on_no_answer=False)

        if not stack:
            return [x.target for x in level_ns_names]
        level_nameservers = get_addresses(level_ns_names, trusted_resolver)
        walking_resolver.nameservers = list(level_nameservers)


if __name__ == '__main__':
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    #res = find_ns('geoguides.geodelic.com')
    res = find_ns('s.geodelic.ws')
    logger.info(pformat(res))


