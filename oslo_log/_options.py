#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy

from oslo_config import cfg

from oslo_log import versionutils

_DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_LOG_LEVELS = ['amqp=WARN', 'amqplib=WARN', 'boto=WARN',
                      'qpid=WARN', 'sqlalchemy=WARN', 'suds=INFO',
                      'oslo.messaging=INFO', 'iso8601=WARN',
                      'requests.packages.urllib3.connectionpool=WARN',
                      'urllib3.connectionpool=WARN', 'websocket=WARN',
                      'requests.packages.urllib3.util.retry=WARN',
                      'urllib3.util.retry=WARN',
                      'keystonemiddleware=WARN', 'routes.middleware=WARN',
                      'stevedore=WARN', 'taskflow=WARN',
                      'keystoneauth=WARN']

_IGNORE_MESSAGE = "This option is ignored if log_config_append is set."

common_cli_opts = [
    cfg.BoolOpt('debug',
                short='d',
                default=False,
                help='If set to true, the logging level will be set to '
                     'DEBUG instead of the default INFO level.'),
    cfg.BoolOpt('verbose',
                short='v',
                default=True,
                help='If set to false, the logging level will be set to '
                     'WARNING instead of the default INFO level.',
                deprecated_for_removal=True),
]

logging_cli_opts = [
    cfg.StrOpt('log-config-append',
               metavar='PATH',
               deprecated_name='log-config',
               help='The name of a logging configuration file. This file '
                    'is appended to any existing logging configuration '
                    'files. For details about logging configuration files, '
                    'see the Python logging module documentation. Note that '
                    'when logging configuration files are used all '
                    'logging configuration is defined in the configuration '
                    'file and other logging configuration options are ignored '
                    '(for example, log_format).'),
    cfg.StrOpt('log-format',
               metavar='FORMAT',
               help='DEPRECATED. '
                    'A logging.Formatter log message format string which may '
                    'use any of the available logging.LogRecord attributes. '
                    'This option is deprecated.  Please use '
                    'logging_context_format_string and '
                    'logging_default_format_string instead. This option is '
                    'ignored if log_config_append is set.'),
    cfg.StrOpt('log-date-format',
               default=_DEFAULT_LOG_DATE_FORMAT,
               metavar='DATE_FORMAT',
               help='Defines the format string for %%(asctime)s in log '
                    'records. Default: %(default)s . '
                    + _IGNORE_MESSAGE),
    cfg.StrOpt('log-file',
               metavar='PATH',
               deprecated_name='logfile',
               help='(Optional) Name of log file to send logging output to. '
                    'If no default is set, logging will go to stderr as '
                    'defined by use_stderr. '
                    + _IGNORE_MESSAGE),
    cfg.StrOpt('log-dir',
               deprecated_name='logdir',
               help='(Optional) The base directory used for relative log_file '
                    ' paths. '
                    + _IGNORE_MESSAGE),
    cfg.BoolOpt('watch-log-file',
                default=False,
                help='Uses logging handler designed to watch file '
                     'system. When log file is moved or removed this handler '
                     'will open a new log file with specified path '
                     'instantaneously. It makes sense only if log_file option '
                     'is specified and Linux platform is used. '
                     + _IGNORE_MESSAGE),
    cfg.BoolOpt('use-syslog',
                default=False,
                help='Use syslog for logging. '
                     'Existing syslog format is DEPRECATED '
                     'and will be changed later to honor RFC5424. '
                     + _IGNORE_MESSAGE),
    cfg.BoolOpt('use-syslog-rfc-format',
                default=True,
                deprecated_for_removal=True,
                help='Enables or disables syslog rfc5424 format '
                     'for logging. If enabled, prefixes the MSG part of the '
                     'syslog message with APP-NAME (RFC5424). The '
                     'format without the APP-NAME is deprecated in Kilo, '
                     'and will be removed in Mitaka, along with this option. '
                     + _IGNORE_MESSAGE),
    cfg.StrOpt('syslog-log-facility',
               default='LOG_USER',
               help='Syslog facility to receive log lines. '
                    + _IGNORE_MESSAGE),
]

generic_log_opts = [
    cfg.BoolOpt('use_stderr',
                default=True,
                help='Log output to standard error. '
                     + _IGNORE_MESSAGE),
]

log_opts = [
    cfg.StrOpt('logging_context_format_string',
               default='%(asctime)s.%(msecs)03d %(process)d %(levelname)s '
                       '%(name)s [%(request_id)s %(user_identity)s] '
                       '%(instance)s%(message)s',
               help='Format string to use for log messages with context.'),
    cfg.StrOpt('logging_default_format_string',
               default='%(asctime)s.%(msecs)03d %(process)d %(levelname)s '
                       '%(name)s [-] %(instance)s%(message)s',
               help='Format string to use for log messages when context is '
                    'undefined.'),
    cfg.StrOpt('logging_debug_format_suffix',
               default='%(funcName)s %(pathname)s:%(lineno)d',
               help='Additional data to append to log message when logging '
                    'level for the message is DEBUG.'),
    cfg.StrOpt('logging_exception_prefix',
               default='%(asctime)s.%(msecs)03d %(process)d ERROR %(name)s '
               '%(instance)s',
               help='Prefix each line of exception output with this format.'),
    cfg.StrOpt('logging_user_identity_format',
               default='%(user)s %(tenant)s '
                       '%(domain)s %(user_domain)s %(project_domain)s',
               help='Defines the format string for %(user_identity)s that '
                    'is used in logging_context_format_string.'),
    cfg.ListOpt('default_log_levels',
                default=DEFAULT_LOG_LEVELS,
                help='List of package logging levels in logger=LEVEL pairs. '
                     + _IGNORE_MESSAGE),
    cfg.BoolOpt('publish_errors',
                default=False,
                help='Enables or disables publication of error events.'),

    # NOTE(mikal): there are two options here because sometimes we are handed
    # a full instance (and could include more information), and other times we
    # are just handed a UUID for the instance.
    cfg.StrOpt('instance_format',
               default='[instance: %(uuid)s] ',
               help='The format for an instance that is passed with the log '
                    'message.'),
    cfg.StrOpt('instance_uuid_format',
               default='[instance: %(uuid)s] ',
               help='The format for an instance UUID that is passed with the '
                    'log message.'),
]


def list_opts():
    """Returns a list of oslo.config options available in the library.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    The purpose of this is to allow tools like the Oslo sample config file
    generator (oslo-config-generator) to discover the options exposed to users
    by this library.

    :returns: a list of (group_name, opts) tuples
    """
    return [(None, copy.deepcopy(common_cli_opts + logging_cli_opts +
                                 generic_log_opts + log_opts +
                                 versionutils.deprecated_opts))]
