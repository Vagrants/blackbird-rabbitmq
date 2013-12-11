#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
detect vhost and queuename and put rabbitmq stats from API
"""

import json
import httplib
import base64
import socket

from blackbird.plugins import base


class ConcreteJob(base.JobBase):
    """
    This Class is required for blackbird plugin module.
    """

    def __init__(self, options, queue=None, logger=None):
        super(ConcreteJob, self).__init__(options, queue, logger)

    def _api_get(self, url):
        """
        Get status from rabbitmq api
        """

        if self.options['ssl']:
            if not 'ssl_key_file' in self.options or not 'ssl_cert_file' in self.options:
                raise ValueError('Pleases specify ssl_key_file and ssl_cert_file...')
            conn = httplib.HTTPSConnection(self.options['api_host'],
                                           self.options['api_port'],
                                           self.options['ssl_key_file'],
                                           self.options['ssl_cert_file'],
                                           timeout=self.options['api_timeout'])
        else:
            conn = httplib.HTTPConnection(self.options['api_host'],
                                          self.options['api_port'],
                                          timeout=self.options['api_timeout'])

        headers = {"Authorization":
                       "Basic " + base64.b64encode(self.options['api_user'] +
                                                   ":" +
                                                   self.options['api_pass'])}

        try:
            conn.request("GET", url, "", headers)
        except socket.error, ex:
            raise Exception("Could not connect: {0}".format(ex))
        resp = conn.getresponse()

        if resp.status != 200:
            raise Exception("Received %d %s for path %s\n%s"
                                  % (resp.status,
                                     resp.reason,
                                     url,
                                     resp.read()))

        return resp.read()

    def _queue_stat(self):
        """
        Get stats of queues
        """

        lld_values = []
        entries = json.loads(self._api_get("/api/queues"))

        if len(entries) == 0:
            self.logger.debug('no message queues found')
            return

        for entry in entries:

            lld_values.append([entry['vhost'], entry['name']])

            for key, value in entry.items():
                items = {
                    "vhost": entry['vhost'],
                    "queuename": entry['name'],
                    "zabbix_key": "rabbitmq.stat.queue"
                }
                item = RabbitmqItem(
                    key=key,
                    value=value,
                    host=self.options['hostname'],
                    items=items
                )
                self.queue.put(item, block=False)

                self.logger.debug(
                    ('Inserted to queue {0}'.format(item.data))
                )

        dis_item = RabbitmqDiscoveryItem(
            key='rabbitmq.stat.queue.LLD',
            value=lld_values,
            host=self.options['hostname'],
            lld_type='queue'
        )
        self.queue.put(dis_item, block=False)

    def _vhost_stat(self):
        """
        Get stats of vhost
        """

        lld_values = []
        entries = json.loads(self._api_get("/api/vhosts"))
        con_status = self._vhost_connection()

        if len(entries) == 0:
            self.logger.debug('no vhost found')
            return

        for entry in entries:

            lld_values.append(entry['name'])

            items = {
                "vhost": entry['name'],
                "zabbix_key": "rabbitmq.stat.vhost"
            }

            for key, value in entry.items():
                if key == "message_stats":
                    for mstats in ["confirm", "publish"]:
                        item = RabbitmqItem(
                                key=mstats,
                                value=value[mstats],
                                host=self.options['hostname'],
                                items=items
                        )
                        self.queue.put(item, block=False)
                else:
                    item = RabbitmqItem(
                        key=key,
                        value=value,
                        host=self.options['hostname'],
                        items=items
                    )
                    self.queue.put(item, block=False)

                self.logger.debug(
                    ('Inserted to queue {0}'.format(item.data))
                )

            for st in ["starting", "tuning", "opening", "running", "blocking",
                       "blocked", "closing", "closed"]:
                con_value = 0
                if entry['name'] in con_status:
                    if st in con_status[entry['name']]:
                        con_value = con_status[entry['name']][st]

                item = RabbitmqItem(
                    key="connection_" + st,
                    value=con_value,
                    host=self.options['hostname'],
                    items=items
                )
                self.queue.put(item, block=False)
                self.logger.debug(
                    ('Inserted to queue {0}'.format(item.data))
                )

        dis_item = RabbitmqDiscoveryItem(
            key='rabbitmq.stat.vhost.LLD',
            value=lld_values,
            host=self.options['hostname'],
            lld_type='vhost'
        )
        self.queue.put(dis_item, block=False)

    def _vhost_connection(self):
        """
        Get stats of vhost connection
        """

        ret = {}
        entries = json.loads(self._api_get("/api/connections"))

        if len(entries) > 0:

            for entry in entries:
                vhost = entry['vhost']
                state = entry['state']
                
                if not vhost in ret:
                    ret[vhost] = {}
                if state in ret[vhost]:
                    ret[vhost][state] += 1
                else:
                    ret[vhost][state] = 1

        return ret

    def looped_method(self):
        """
        Get stats data of rabbitmq.
        Method name must be "looped_method".
        """

        self._queue_stat()
        self._vhost_stat()

        self.logger.info('Enqueued RabbitmqValue')


class RabbitmqItem(base.ItemBase):
    """
    Enqueued item. This Class has required attribute "data".
    """

    def __init__(self, key, value, host, items):
        super(RabbitmqItem, self).__init__(key, value, host)

        self.__data = dict()
        self.items = items
        if 'queuename' in items:
            self._generate_queue()
        else:
            self._generate()

    @property
    def data(self):

        return self.__data

    def _generate(self):
        self.__data['host'] = self.host
        self.__data['key'] = (
            '{zabbix_key}[{vhost},{key}]'
            ''.format(zabbix_key=self.items['zabbix_key'],
                           vhost=self.items['vhost'],
                             key=self.key)
        )
        self.__data['value'] = self.value

    def _generate_queue(self):
        self.__data['host'] = self.host
        self.__data['key'] = (
            '{zabbix_key}[{vhost},{queuename},{key}]'
            ''.format(zabbix_key=self.items['zabbix_key'],
                           vhost=self.items['vhost'],
                       queuename=self.items['queuename'],
                             key=self.key)
        )
        self.__data['value'] = self.value


class RabbitmqDiscoveryItem(base.ItemBase):
    """
    Queue Item for "zabbix discovery".
    """

    def __init__(self, key, value, host, lld_type):
        super(RabbitmqDiscoveryItem, self).__init__(key, value, host)

        self.__data = dict()
        self._generate(lld_type)

    @property
    def data(self):
        return self.__data

    def _generate(self, lld_type):
        self.__data['host'] = self.host
        self.__data['clock'] = self.clock
        self.__data['key'] = self.key

        if lld_type == "queue":
            value = {
                'data': [{'{#VHOST}': v[0],'{#QUEUENAME}': v[1]} for v in self.value],
            }
        else:
            value = {
                'data': [{'{#VHOST}': v} for v in self.value],
            }

        self.__data['value'] = json.dumps(value)


class Validator(base.ValidatorBase):
    """
    Check whether the your config file value is invalid.
    """

    def __init__(self):
        self.__spec = None

    @property
    def spec(self):
        self.__spec = (
            "[{0}]".format(__name__),
            "api_user = string(default='guest')",
            "api_pass = string(default='guest')",
            "api_host = string(default='localhost')",
            "api_port = integer(0, 65535, default=15672)",
            "api_timeout = integer(0, 600, default=3)",
            "ssl = boolean(default=False)",
            "hostname = string(default={0})".format(self.gethostname()),
        )
        return self.__spec

