import logging
import dateutil.parser
from datetime import datetime, timedelta
from pprint import pprint
from boto import ec2
from boto.exception import EC2ResponseError 

import config

logger = logging.getLogger(__name__)

class EC2_Account_Connection(object):
    def __init__(self, aws_access_id=None, aws_secret_key=None, regions=[]):
        self.aws_access_id = aws_access_id
        self.aws_secret_key = aws_secret_key
        self.regions = regions
        self.connections = {}
        for region in self.regions:
            try:
                self.connections[region] = ec2.connect_to_region(region,
                                                 aws_access_key_id=self.aws_access_id,
                                                 aws_secret_access_key=self.aws_secret_key)
                logger.debug('EC2 connection established: %s' % region)
            except Exception, e:
                logger.error('EC2 connection failed to %s: %s' % (region, e))
                raise Exception(e)

    def get_instances(self, age_filter=0, filters={'instance-state-name': 'running'}):
        """
        Queries AWS for running instances across all regions.
        age_filter is number of days that instance must have existed to be counted.

        Returns a dictionary like:
        { availability_zone1: { instance_type1: count, instance_type2: count, ... },
          availability_zone2: { instance_type1: count, instance_type2: count, ... } }
        """
        _result = {}
        for region, conn in self.connections.iteritems():
            try:
                _instances = [i for res in
                               conn.get_all_instances(filters=filters) for i in res.instances
                               if self._check_instance(i, age_filter)]
            except EC2ResponseError, e:
                logger.warning("{0}: Instance(s) {1} not found.".format(region, instance_ids))
                continue
            for i in _instances:
                _az = i.placement
                _type = i.instance_type
                if _result.get(_az):
                    if _result[_az].get(_type):
                        _result[_az][_type] += 1
                    else:
                        _result[_az][_type] = 1
                else:
                    _result[_az] = {_type: 1}
        self.instances = _result
        return self.instances

    def _check_instance(self, instance, age_filter):
        if not instance.id:
            return False
        # make sure instance is older than age_filter
        launch_time = dateutil.parser.parse(instance.launch_time, ignoretz=True)
        if launch_time < (datetime.now() + timedelta(days=-age_filter)):
            return True
        return False

    def get_reservations(self, offeringType=None):
        """
        Queries AWS for all existing reservations. Returns a dictionary like this:
        { availability_zone1: { instance_type1: count, instance_type2: count, ... },
          availability_zone2: { instance_type1: count, instance_type2: count, ... } }

        where the counts are summerized across reservation purchases.
        """
        _result = {}
        for region, conn in self.connections.iteritems():
            try:
                _reservations = conn.get_all_reserved_instances()
            except EC2ResponseError, e:
                logger.warning("{0}: Reservations(s) {1} not found.".format(region))
                continue
            for r in _reservations:
                if r.state != 'active':
                    # we don't want to count inactive reservations
                    continue
                if offeringType and r.offering_type != offeringType:
                    continue
                _az = r.availability_zone
                _type = r.instance_type
                if _result.get(_az):
                    # we already have an active RI for this AZ.
                    if _result[_az].get(_type):
                        # already have an RI for this AZ and type. Sum.
                        _result[_az][_type] += r.instance_count
                    else:
                        _result[_az][_type] = r.instance_count
                else:
                    _result[_az] = {_type: r.instance_count}
        self.reservations = _result
        return self.reservations

def dict_sum(d1, d2):
    """ takes two dictionaries like
    d1 = { a: 1, b: 2 }
    d2 = { a: 3, c: 5 }

    and returns:
    { a: 4, b:2, c:5 }
    """
    result = dict(d1)
    for k,v in d2.iteritems():
        if result.get(k):
            result[k] = result[k] + v
        else:
            result[k] = v
    return result

def dict_diff(d1, d2):
    """ takes two dictionaries like
    d1 = { a: 1, b: 2 }
    d2 = { a: 3, c: 5 }

    and returns:
    { a: -2, b:2, c:-5 }
    """
    result = dict(d1)
    for k,v in d2.iteritems():
        if result.get(k):
            result[k] = result[k] - v
        else:
            result[k] = -v
    return result

if __name__ == "__main__":
    total = {}
    availability_zones = set()
    instance_types = set()
    for account in config.CREDENTIALS:
        print "Account: {0}".format(account['name'])
        conn = EC2_Account_Connection(aws_access_id=account['access_id'],
                                      aws_secret_key=account['secret_key'],
                                      regions=config.REGIONS)
        running = conn.get_instances(age_filter=config.AGE_FILTER)
        reserved = conn.get_reservations(offeringType=config.OFFERINGTYPE)
        availability_zones |= set(running.keys()) | set(reserved.keys())
        for types in running.itervalues():
            instance_types |= set(types.keys())
        for types in reserved.itervalues():
            instance_types |= set(types.keys())
        print ',' + ',,,'.join(sorted(instance_types))
        for az in sorted(availability_zones):
            print "{0},".format(az),
            try:
                _running = running[az]
            except KeyError:
                _running = {}
            try:
                _reserved = reserved[az]
            except KeyError:
                _reserved = {}
            diff = dict_diff(_running, _reserved)
            for instance_type in sorted(instance_types):
                if instance_type in diff:
                    _run_count = _running.get(instance_type)
                    _res_count = _reserved.get(instance_type)
                    print "{0},{1},{2},".format(_run_count if _run_count else '0',
                                                _res_count if _res_count else '0',
                                                diff[instance_type]),
                else:
                    print "0,0,0,",
            print ""

            if not total.get('running'):
                total['running'] = {}
            if total['running'].get(az):
                total['running'][az] = dict_sum(total['running'][az], _running)
            else:
                total['running'][az] = _running

            if not total.get('reserved'):
                total['reserved'] = {}
            if total['reserved'].get(az):
                total['reserved'][az] = dict_sum(total['reserved'][az], _reserved)
            else:
                total['reserved'][az] = _reserved

    print ""
    print "total (consolidated view)"
    print "================================================"
    print ',' + ',,,'.join(sorted(instance_types))
    for az in sorted(availability_zones):
        print "{0},".format(az),
        try:
            _running = total['running'][az]
        except KeyError:
            _running = {}
        try:
            _reserved = total['reserved'][az]
        except KeyError:
            _reserved = {}
        diff = dict_diff(_running, _reserved)
        for instance_type in sorted(instance_types):
            if instance_type in diff:
                _run_count = _running.get(instance_type)
                _res_count = _reserved.get(instance_type)
                print "{0},{1},{2},".format(_run_count if _run_count else '0',
                                            _res_count if _res_count else '0',
                                            diff[instance_type]),
            else:
                print "0,0,0,",
        print ""
