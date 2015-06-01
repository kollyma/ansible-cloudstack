#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: cs_network
short_description: Manages networks on Apache CloudStack based clouds.
description: create, delete or modify networks
version_added: '0.1'
options:
options:
  name:
    description:
      - Name of the Network.
    required: true
  display_name:
    description:
      - Description of the Network.
    required: false
    default: null
  network_offering:
    description:
      - Name or ID of the network offering
    required: yes
  zone:
    description:
      - Name of the zone, where the network should be deployed
    required: yes
    default: null
  state:
      - State of the network
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  project:
      - Name of the project, where the network should be deployed
    required: false
    default: false
  domain:
      - Name of the Domain, where the network should be deployed
'''

EXAMPLES = '''
---
'''


try:
    from cs import CloudStack, CloudStackException, read_config
    has_lib_cs = True
except ImportError:
    has_lib_cs = False


class AnsibleCloudStack:

    def __init__(self, module):
        if not has_lib_cs:
            module.fail_json(msg="python library cs required: pip install cs")

        self.module = module
        self._connect()
        self.project_id = None
        self.network_id = None
        self.ip_address_id = None
        self.zone_id = None
        self.vm_id = None
        self.os_type_id = None
        self.hypervisor = None


    def _connect(self):
        api_key = self.module.params.get('api_key')
        api_secret = self.module.params.get('secret_key')
        api_url = self.module.params.get('api_url')
        api_http_method = self.module.params.get('api_http_method')

        if api_key and api_secret and api_url:
            self.cs = CloudStack(
                endpoint=api_url,
                key=api_key,
                secret=api_secret,
                method=api_http_method
                )
        else:
            self.cs = CloudStack(**read_config())


    def get_project_id(self):
        if self.project_id:
            return self.project_id

        project = self.module.params.get('project')
        if not project:
            return None

        projects = self.cs.listProjects()
        if projects:
            for p in projects['project']:
                if project in [ p['name'], p['displaytext'], p['id'] ]:
                    self.project_id = p['id']
                    return self.project_id
        self.module.fail_json(msg="project '%s' not found" % project)


    def get_zone_id(self):
        if self.zone_id:
            return self.zone_id
        zone = self.module.params.get('zone')
        zones = self.cs.listZones()
        # use the first zone if no zone param given
        if not zone:
            self.zone_id = zones['zone'][0]['id']
            return self.zone_id
        if zones:
            for z in zones['zone']:
                if zone in [ z['name'], z['id'] ]:
                    self.zone_id = z['id']
                    return self.zone_id
        self.module.fail_json(msg="zone '%s' not found" % zone)

    def _poll_job(self, job=None, key=None):
        if 'jobid' in job:
            while True:
                res = self.cs.queryAsyncJobResult(jobid=job['jobid'])
                if res['jobstatus'] != 0 and 'jobresult' in res:
                    if 'errortext' in res['jobresult']:
                        self.module.fail_json(msg="Failed: '%s'" % res['jobresult']['errortext'])
                    if key and key in res['jobresult']:
                        job = res['jobresult'][key]
                    break
                time.sleep(2)
        return job

class AnsibleCloudStackNetwork(AnsibleCloudStack):

    def __init__(self, module):
        AnsibleCloudStack.__init__(self, module)
        self.result = {
            'changed': False,
        }
        self.iso = None

    def create_network(self):
        network = self.get_network()
        if not network:
            self.result['changed'] = True
            args = {}
            args['displaytext'] = self.module.params.get('display_name')
            args['name'] = self.module.params.get('name')
            args['projectid'] = self.get_project_id()
            args['zoneid'] = self.get_zone_id()
            args['networkofferingid'] = self.get_network_offering_id()
            if not self.module.check_mode:
                network = self.cs.createNetwork(**args)
                if 'errortext' in network:
                    self.module.fail_json(msg="Failed: '%s'" % network['errortext'])
                poll_async = self.module.params.get('poll_async')
                if poll_async:
                    network = self._poll_job(network, 'network')
            return network

    def remove_network(self):
        network = self.get_network()
        if network:
            self.result['changed'] = True
            if not self.module.check_mode:
                network = self.cs.deleteNetwork(id=network['id'])
		if 'errortext' in network:
                   self.module.fail_json(msg="Failed: '%s'" % network['errortext'])
                poll_async = self.module.params.get('poll_async')
                if poll_async:
                    network = self._poll_job(network, 'network')
            return network

    def get_network(self):
        args = {}
        args['name'] = self.module.params.get('name')
        args['state'] = self.module.params.get('state')
        networks = self.cs.listNetworks()
        if networks:
            for n in networks['network']:
                if args['name'] in [ n['name'], n['id'] ]:
                    return n
        return None
        
    def get_network_offering_id(self):
        network_offering = self.module.params.get('network_offering')

        network_offerings = self.cs.listNetworkOfferings()
        if network_offerings:
            if not network_offering:
                return network_offerings['networkoffering'][0]['id']

            for n in network_offerings['networkoffering']:
                if network_offering in [ n['name'], n['id'] ]:
                    return n['id']
        self.module.fail_json(msg="Network offering '%s' not found" % network_offering)
        

    def get_result(self, network):
        if network:
            if 'id' in network:
                self.result['id'] = network['id']
            if 'name' in network:
                self.result['name'] = network['name']
            if 'displayname' in network:
                self.result['display_name'] = network['displayname']
        return self.result


    def get_network_id(self):
        if self.network_id:
            return self.network_id
        
        network = self.module.params.get('name')
        if not network:
            return None

        networks = self.cs.listNetworks()
        if networks:
            for n in networks['network']:
                if network in [ n['name'], n['displaytext'], n['id'] ]:
                    self.network_id = n['id']
                    return self.network_id
        self.module.fail_json(msg="network '%s' not found" % network)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required=True),
            display_name = dict(default=None),
            network_offering = dict(required=True),
            zone = dict(required=True),
            project = dict(default=None),
            domain = dict(default=None),
            state = dict(choices=['present', 'absent'], default='present'),
            tags = dict(type='list', aliases=[ 'tag' ], default=None),
            poll_async = dict(choices=BOOLEANS, default=True),
            api_key = dict(default=None),
            api_secret = dict(default=None),
            api_url = dict(default=None),
            api_http_method = dict(default='get'),
        ),
        supports_check_mode=True
    )

    if not has_lib_cs:
        module.fail_json(msg="python library cs required: pip install cs")

    try:
        acs_network = AnsibleCloudStackNetwork(module)

        state = module.params.get('state')
        if state in ['absent']:
            network = acs_network.remove_network()
        else:
            network = acs_network.create_network()

        result = acs_network.get_result(network)  

    except CloudStackException, e:
        module.fail_json(msg='CloudStackException: %s' % str(e))

    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
