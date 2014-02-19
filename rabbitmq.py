#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# pylint: disable=C0111,C0301,R0903

__VERSION__ = '0.1.4'

import requests
import json

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

        # ping item
        self._ping()

        # detect rabbitmq and erlang version
        self._get_version()

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

    def _enqueue(self, key, value):
        """
        put into queue
        """

        item = RabbitmqItem(
            key=key,
            value=value,
            host=self.options['hostname']
        )
        self.queue.put(item, block=False)
        self.logger.debug(
            'Inserted to queue {key}:{value}'
            ''.format(key=item.key, value=item.value)
        )

    def _enqueue_lld(self, key, value):

        item = base.DiscoveryItem(
            key=key,
            value=value,
            host=self.options['hostname']
        )
        self.queue.put(item, block=False)
        self.logger.debug(
            'Inserted to lld queue {key}:{value}'
            ''.format(key=key, value=str(value))
        )

    def _ping(self):
        """
        send ping item
        """

        self._enqueue('blackbird.rabbitmq.ping', 1)
        self._enqueue('blackbird.rabbitmq.version', __VERSION__)

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

    def _get_version(self):
        """
        Get version from overview
        """

        overview = json.loads(self._request('/api/overview'))

        if overview:

            if 'rabbitmq_version' in overview:
                self._enqueue('rabbitmq.version', overview['rabbitmq_version'])
            else:
                self._enqueue('rabbitmq.version', 'Unknown')

            if 'management_version' in overview:
                self._enqueue(
                    'rabbitmq.management.version',
                    overview['management_version']
                )
            else:
                self._enqueue('rabbitmq.management.version', 'Unknown')

            if 'erlang_version' in overview:
                self._enqueue(
                    'rabbitmq.erlang.version',
                    overview['erlang_version']
                )
            else:
                self._enqueue('rabbitmq.erlang.version', 'Unknown')

            if 'erlang_full_version' in overview:
                self._enqueue(
                    'rabbitmq.erlang.full.version',
                    overview['erlang_full_version']
                )
            else:
                self._enqueue('rabbitmq.erlang.full.version', 'Unknown')

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

                # message_stats
                if 'message_stats' in entry:
                    self._enqueue(
                        'rabbitmq.stat.vhost[{0},message_stats,confirm]'
                        ''.format(vhost),
                        entry['message_stats']['confirm']
                    )
                    self._enqueue(
                        'rabbitmq.stat.vhost[{0},message_stats,confirm,rate]'
                        ''.format(vhost),
                        entry['message_stats']['confirm']['rate']
                    )
                    self._enqueue(
                        'rabbitmq.stat.vhost[{0},message_stats,publish]'
                        ''.format(vhost),
                        entry['message_stats']['publish']
                    )
                    self._enqueue(
                        'rabbitmq.stat.vhost[{0},message_stats,publish,rate]'
                        ''.format(vhost),
                        entry['message_stats']['publish']['rate']
                    )

                # other items
                for key in ['messages', 'messages_ready',
                            'messages_unacknowledged',
                            'recv_oct', 'send_oct']:
                    if key in entry:
                        self._enqueue(
                            'rabbitmq.stat.vhost[{0},{1}]'.format(vhost, key),
                            entry[key]
                        )
                        self._enqueue(
                            'rabbitmq.stat.vhost[{0},{1},rate]'
                            ''.format(vhost, key),
                            entry['{0}_details'.format(key)]['rate']
                        )

                # tracing
                self._enqueue('rabbitmq.stat.vhost[{0},tracing]'.format(vhost),
                              entry['tracing'])

                # set connection info
                for status in ['starting', 'tuning', 'opening', 'running',
                               'blocking', 'blocked', 'closing', 'closed']:
                    status_value = 0
                    if vhost in con_status:
                        if status in con_status[vhost]:
                            status_value = con_status[vhost][status]

                    self._enqueue(
                        'rabbitmq.stat.vhost[{0},connection_{1}]'
                        ''.format(vhost, status),
                        status_value
                    )

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
                        "starting": 0,
                        "tuning": 0,
                        "opening": 0,
                        "running": 0,
                        "blocking": 0,
                        "blocked": 0,
                        "closing": 0,
                        "closed": 0,
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
                            "idle_since", "memory", "status"]:
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},{2}]'
                        ''.format(vhost, name, key),
                        entry[key]
                    )

                # backing_queue_status
                for key in entry['backing_queue_status']:
                    if key == 'delta':
                        continue
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},backing_queue_status,{2}]'
                        ''.format(vhost, name, key),
                        entry['backing_queue_status'][key]
                    )

                # messages
                if 'messages' in entry:
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},messages]'
                        ''.format(vhost, name),
                        entry['messages']
                    )
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},messages,rate]'
                        ''.format(vhost, name),
                        entry['messages_details']['rate']
                    )
                # messages_ready
                if 'messages_ready' in entry:
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},messages_ready]'
                        ''.format(vhost, name),
                        entry['messages_ready']
                    )
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},messages_ready,rate]'
                        ''.format(vhost, name),
                        entry['messages_ready_details']['rate']
                    )

                # message_stats
                if 'message_stats' in entry:
                    self._enqueue(
                        'rabbitmq.stat.queue[{0},{1},message_stats,publish]'
                        ''.format(vhost, name),
                        entry['message_stats']['publish']
                    )
                    self._enqueue(
                        'rabbitmq.stat.queue'
                        '[{0},{1},message_stats,publish,rate]'
                        ''.format(vhost, name),
                        entry['message_stats']['publish']['rate']
                    )

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
            self._enqueue_lld(
                'rabbitmq.vhost.LLD',
                [{'{#VHOST}': vhost} for vhost in lld_vhosts]
            )

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
            self._enqueue_lld(
                'rabbitmq.queue.LLD',
                [{'{#VHOST}': v[0], '{#QUEUENAME}': v[1]} for v in lld_queues]
            )


class RabbitmqItem(base.ItemBase):
    """
    Enqueued item. This Class has required attribute "data".
    """

    def __init__(self, key, value, host):
        super(RabbitmqItem, self).__init__(key, value, host)

        self.__data = dict()
        self._generate()

    @property
    def data(self):
        return self.__data

    def _generate(self):
        self.__data['key'] = self.key
        if isinstance(self.value, bool):
            self.__data['value'] = int(self.value)
        else:
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
            "api_port = integer(0, 65535, default=15672)",
            "timeout = integer(0, 600, default=3)",
            "hostname = string(default={0})".format(self.detect_hostname()),
        )
        return self.__spec
