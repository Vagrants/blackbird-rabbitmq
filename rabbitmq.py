#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
detect vhost and queuename and put rabbitmq stats from API
"""

import requests
import json
import re

from blackbird.plugins import base

class ConcreteJob(base.JobBase):
    """
    This Class is called by "Executor"
    Get rabbitmq's info,
    and send to specified zabbix server.
    """

    def __init__(self, options, queue=None, logger=None):
        super(ConcreteJob, self).__init__(options, queue, logger)

    def build_items(self):
        """
        main loop
        """

        # get vhost status
        self._vhost_stat()

        # get queue status
        self._queue_stat()

    def build_discovery_items(self):
        """
        main loop for lld
        """

        # lld vhost name
        self._vhost_lld()

        # lld queue name
        self._queue_lld()

    def _enqueue(self, item):
        """
        put into queue
        """

        self.queue.put(item, block=False)
        self.logger.debug(
            'Inserted to queue {key}:{value}'
            ''.format(key=item.key, value=item.value)
        )

    def _request(self, uri):
        """
        Request http connection and return contents.
        """

        auth = (self.options['api_user'], self.options['api_pass'])
        url = (
            'http://{host}:{port}{uri}'
            ''.format(
                host=self.options['api_host'],
                port=self.options['api_port'],
                uri=uri
            )
        )

        try:
            response = requests.get(url,
                                    timeout=self.options['timeout'],
                                    auth=auth,
                                    verify=False)
        except requests.exceptions.RequestException:
            self.logger.error(
                'Can not connect to {url}'
                ''.format(url=url)
            )
            return None

        if response.status_code == 200:
            return response.content
        else:
            self.logger.error(
                'Can not get status from {url} status:{status}'
                ''.format(url=url, status=response.status_code)
            )
            return None

    def _vhost_stat(self):
        """
        Get stats of vhost
        """

        # get connection status from api
        con_status = self._vhost_connection()

        api_body = self._request('/api/vhosts')
        if api_body:
            for entry in json.loads(api_body):

                vhost = entry['name']

                for key, value in entry.items():
                    if key == 'message_stats':
                        for mstats in ['confirm', 'publish']:
                            item = RabbitmqVhostItem(
                                    key='{0},{1}'.format(vhost, mstats),
                                    value=value[mstats],
                                    host=self.options['hostname'],
                            )
                            self._enqueue(item)
                    elif key == 'name':
                        continue
                    elif re.search(r'_details$', key):
                        continue
                    else:
                        item = RabbitmqVhostItem(
                            key='{0},{1}'.format(vhost, key),
                            value=value,
                            host=self.options['hostname']
                        )
                        self._enqueue(item)

                # set connection info
                for status in ['starting', 'tuning', 'opening', 'running', 'blocking',
                               'blocked', 'closing', 'closed']:
                    status_value = 0
                    if vhost in con_status:
                        if status in con_status[vhost]:
                            status_value = con_status[vhost][status]

                    item = RabbitmqVhostItem(
                        key='{0},connection_{1}'.format(vhost, status),
                        value=status_value,
                        host=self.options['hostname'],
                    )
                    self._enqueue(item)

    def _vhost_connection(self):
        """
        Get stats of vhost connection
        """

        con_hash = {}

        api_body = self._request('/api/connections')
        if api_body:
            for entry in json.loads(api_body):

                vhost = entry['vhost']
                state = entry['state']
                
                if not vhost in con_hash:
                    con_hash[vhost] = {
                        "starting":0,
                        "tuning":0,
                        "opening":0,
                        "running":0,
                        "blocking":0,
                        "blocked":0,
                        "closing":0,
                        "closed":0,
                    }

                con_hash[vhost][state] += 1

        return con_hash

    def _queue_stat(self):
        """
        Get stats of queues
        """

        api_body = self._request('/api/queues')
        if api_body:
            for entry in json.loads(api_body):

                # Queue name
                name = entry['name']

                # Virtual host this queue belongs to
                vhost = entry['vhost']

                for key in ["auto_delete", "consumers", "durable",
                            "idle_since", "memory", "messages",
                            "messages_ready", "status"]:
                    item = RabbitmqQueueItem(
                        key='{0},{1},{2}'.format(vhost, name, key),
                        value=entry[key],
                        host=self.options['hostname'],
                    )
                    self._enqueue(item)

                # backing_queue_status
                for key in entry['backing_queue_status']:
                    if key == 'delta':
                        continue
                    item = RabbitmqQueueItem(
                        key='{0},{1},backing_queue_status,{2}'.format(vhost, name, key),
                        value=entry['backing_queue_status'][key],
                        host=self.options['hostname'],
                    )
                    self._enqueue(item)

                # message_stats
                item = RabbitmqQueueItem(
                    key='{0},{1},message_stats,publish'.format(vhost, name),
                    value=entry['message_stats']['publish'],
                    host=self.options['hostname'],
                )
                self._enqueue(item)
                item = RabbitmqQueueItem(
                    key='{0},{1},message_stats,publish,rate'.format(vhost, name),
                    value=entry['message_stats']['publish_details']['rate'],
                    host=self.options['hostname'],
                )
                self._enqueue(item)

                # messages_details rate
                item = RabbitmqQueueItem(
                    key='{0},{1},messages,rate'.format(vhost, name),
                    value=entry['messages_details']['rate'],
                    host=self.options['hostname'],
                )
                self._enqueue(item)

                # messages_ready_details rate
                item = RabbitmqQueueItem(
                    key='{0},{1},messages_ready,rate'.format(vhost, name),
                    value=entry['messages_ready_details']['rate'],
                    host=self.options['hostname'],
                )
                self._enqueue(item)

    def _vhost_lld(self):
        """
        Discovery vhost name
        """

        lld_vhosts = []

        api_body = self._request('/api/vhosts')
        if api_body:
            for entry in json.loads(api_body):
                lld_vhosts.append(entry['name'])

        if len(lld_vhosts) > 0:
            item = base.DiscoveryItem(
                key='rabbitmq.vhost.LLD',
                value=[{'{#VHOST}': vhost} for vhost in lld_vhosts],
                host=self.options['hostname']
            )
            self._enqueue(item)

    def _queue_lld(self):
        """
        Discovery queue name
        """

        lld_queues = []

        api_body = self._request('/api/queues')
        if api_body:
            for entry in json.loads(api_body):
                lld_queues.append([entry['vhost'], entry['name']])

        if len(lld_queues) > 0:
            item = base.DiscoveryItem(
                key='rabbitmq.queue.LLD',
                value=[{'{#VHOST}': value[0], '{#QUEUENAME}': value[1]} for value in lld_queues],
                host=self.options['hostname']
            )
            self._enqueue(item)


class RabbitmqVhostItem(base.ItemBase):
    """
    Enqueued item. This Class has required attribute "data".
    """

    def __init__(self, key, value, host):
        super(RabbitmqVhostItem, self).__init__(key, value, host)

        self.__data = dict()
        self._generate()

    @property
    def data(self):
        return self.__data

    def _generate(self):
        self.__data['key'] = 'rabbitmq.stat.vhost[{0}]'.format(self.key)
        self.__data['value'] = self.value
        self.__data['host'] = self.host


class RabbitmqQueueItem(base.ItemBase):
    """
    Enqueued item. This Class has required attribute "data".
    """

    def __init__(self, key, value, host):
        super(RabbitmqQueueItem, self).__init__(key, value, host)

        self.__data = dict()
        self._generate()

    @property
    def data(self):
        return self.__data

    def _generate(self):
        self.__data['key'] = 'rabbitmq.stat.queue[{0}]'.format(self.key)
        self.__data['value'] = self.value
        self.__data['host'] = self.host


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
            "api_port = integer(1, 65535, default=15672)",
            "timeout = integer(0, 600, default=3)",
            "hostname = string(default={0})".format(self.detect_hostname()),
        )
        return self.__spec

