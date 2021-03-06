#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2015, Darren Worrall <darren@iweb.co.uk>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible. If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: cs_ip_address
short_description: Manages Public/Secondary IP address associations
description:
    - Acquires and associates a public IP to an account or project. Due to API
      limitations this is not an idempotent call, so be sure to only
      conditionally call this when C(state=present)
version_added: '2.0'
author: "Darren Worrall @dazworrall"
options:
  ip_address:
    description:
      - Public IP address. Required if C(state=absent)
    required: false
    default: null
  domain:
    description:
      - Domain the IP address is related to.
    required: false
    default: null
  network:
    description:
      - Network the IP address is related to.
    required: false
    default: null
  account:
    description:
      - Account the IP address is related to.
    required: false
    default: null
  project:
    description:
      - Name of the project the IP address is related to.
    required: false
    default: null
  zone:
    description:
      - Name of the zone in which the IP address is in.
      - If not set, default zone is used.
    required: false
    default: null
  poll_async:
    description:
      - Poll async jobs until job has finished.
    required: false
    default: true
extends_documentation_fragment: cloudstack
'''

EXAMPLES = '''
# Associate an IP address
- local_action:
    module: cs_ip_address
    network: My Network
  register: ip_address
  when: instance.public_ip is undefined

# Disassociate an IP address
- local_action:
    module: cs_ip_address
    ip_address: 1.2.3.4
    state: absent
'''

RETURN = '''
---
ip_address:
  description: Public IP address.
  returned: success
  type: string
  sample: 1.2.3.4
zone:
  description: Name of zone the IP address is related to.
  returned: success
  type: string
  sample: ch-gva-2
project:
  description: Name of project the IP address is related to.
  returned: success
  type: string
  sample: Production
account:
  description: Account the IP address is related to.
  returned: success
  type: string
  sample: example account
domain:
  description: Domain the IP address is related to.
  returned: success
  type: string
  sample: example domain
'''


try:
    from cs import CloudStack, CloudStackException, read_config
    has_lib_cs = True
except ImportError:
    has_lib_cs = False

# import cloudstack common
from ansible.module_utils.cloudstack import *


class AnsibleCloudStackIPAddress(AnsibleCloudStack):

    #TODO: Add to parent class, duplicated in cs_network
    def get_network(self, key=None, network=None):
        if not network:
            network = self.module.params.get('network')

        if not network:
            return None

        args                = {}
        args['account']     = self.get_account('name')
        args['domainid']    = self.get_domain('id')
        args['projectid']   = self.get_project('id')
        args['zoneid']      = self.get_zone('id')

        networks = self.cs.listNetworks(**args)
        if not networks:
            self.module.fail_json(msg="No networks available")

        for n in networks['network']:
            if network in [ n['displaytext'], n['name'], n['id'] ]:
                return self._get_by_key(key, n)
                break
        self.module.fail_json(msg="Network '%s' not found" % network)

    #TODO: Merge changes here with parent class
    def get_ip_address(self, key=None):
        if self.ip_address:
            return self._get_by_key(key, self.ip_address)

        ip_address = self.module.params.get('ip_address')
        if not ip_address:
            self.module.fail_json(msg="IP address param 'ip_address' is required")

        args = {}
        args['ipaddress'] = ip_address
        args['account'] = self.get_account(key='name')
        args['domainid'] = self.get_domain(key='id')
        args['projectid'] = self.get_project(key='id')
        ip_addresses = self.cs.listPublicIpAddresses(**args)

        if ip_addresses:
            self.ip_address = ip_addresses['publicipaddress'][0]
        return self._get_by_key(key, self.ip_address)

    def associate_ip_address(self):
        self.result['changed'] = True
        args = {}
        args['account'] = self.get_account(key='name')
        args['domainid'] = self.get_domain(key='id')
        args['projectid'] = self.get_project(key='id')
        args['networkid'] = self.get_network(key='id')
        args['zoneid'] = self.get_zone(key='id')
        ip_address = {}
        if not self.module.check_mode:
            res = self.cs.associateIpAddress(**args)
            if 'errortext' in res:
                self.module.fail_json(msg="Failed: '%s'" % res['errortext'])

            poll_async = self.module.params.get('poll_async')
            if poll_async:
                res = self._poll_job(res, 'ipaddress')
            ip_address = res
        return ip_address

    def disassociate_ip_address(self):
        ip_address = self.get_ip_address()
        if ip_address is None:
            return ip_address
        if ip_address['isstaticnat']:
            self.module.fail_json(msg="IP address is allocated via static nat")

        self.result['changed'] = True
        if not self.module.check_mode:
            res = self.cs.disassociateIpAddress(id=ip_address['id'])
            if 'errortext' in res:
                self.module.fail_json(msg="Failed: '%s'" % res['errortext'])
            poll_async = self.module.params.get('poll_async')
            if poll_async:
                res = self._poll_job(res, 'ipaddress')
        return ip_address

    def get_result(self, ip_address):
        if ip_address:
            if 'zonename' in ip_address:
                self.result['zone'] = ip_address['zonename']
            if 'domain' in ip_address:
                self.result['domain'] = ip_address['domain']
            if 'account' in ip_address:
                self.result['account'] = ip_address['account']
            if 'project' in ip_address:
                self.result['project'] = ip_address['project']
            if 'ipaddress' in ip_address:
                self.result['ip_address'] = ip_address['ipaddress']
            if 'id' in ip_address:
                self.result['id'] = ip_address['id']
        return self.result


def main():
    module = AnsibleModule(
        argument_spec = dict(
            ip_address = dict(required=False),
            state = dict(choices=['present', 'absent'], default='present'),
            zone = dict(default=None),
            domain = dict(default=None),
            account = dict(default=None),
            network = dict(default=None),
            project = dict(default=None),
            poll_async = dict(choices=BOOLEANS, default=True),
            api_key = dict(default=None),
            api_secret = dict(default=None, no_log=True),
            api_url = dict(default=None),
            api_http_method = dict(choices=['get', 'post'], default='get'),
            api_timeout = dict(type='int', default=10),
        ),
        required_together = (
            ['api_key', 'api_secret', 'api_url'],
        ),
        supports_check_mode=True
    )

    if not has_lib_cs:
        module.fail_json(msg="python library cs required: pip install cs")

    try:
        acs_ip_address = AnsibleCloudStackIPAddress(module)

        state = module.params.get('state')
        if state in ['absent']:
            ip_address = acs_ip_address.disassociate_ip_address()
        else:
            ip_address = acs_ip_address.associate_ip_address()

        result = acs_ip_address.get_result(ip_address)

    except CloudStackException, e:
        module.fail_json(msg='CloudStackException: %s' % str(e))

    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
