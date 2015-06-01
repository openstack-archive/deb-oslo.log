# Copyright 2011 OpenStack Foundation.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
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

"""OpenStack logging handler.

This module adds to logging functionality by adding the option to specify
a context object when calling the various log methods.  If the context object
is not specified, default formatting is used. Additionally, an instance uuid
may be passed as part of the log message, which is intended to make it easier
for admins to find messages related to a specific instance.

It also allows setting of formatting information through conf.

"""

import logging
import logging.config
import logging.handlers
import os
import sys
import syslog
import traceback

from oslo_config import cfg
from oslo_utils import encodeutils
from oslo_utils import importutils
import six
from six import moves

_PY26 = sys.version_info[0:2] == (2, 6)

from oslo_log._i18n import _
from oslo_log import _options
from oslo_log import formatters
from oslo_log import handlers


def _get_log_file_path(conf, binary=None):
    logfile = conf.log_file
    logdir = conf.log_dir

    if logfile and not logdir:
        return logfile

    if logfile and logdir:
        return os.path.join(logdir, logfile)

    if logdir:
        binary = binary or handlers._get_binary_name()
        return '%s.log' % (os.path.join(logdir, binary),)

    return None


class BaseLoggerAdapter(logging.LoggerAdapter):

    warn = logging.LoggerAdapter.warning

    @property
    def handlers(self):
        return self.logger.handlers

    def isEnabledFor(self, level):
        if _PY26:
            # This method was added in python 2.7 (and it does the exact
            # same logic, so we need to do the exact same logic so that
            # python 2.6 has this capability as well).
            return self.logger.isEnabledFor(level)
        else:
            return super(BaseLoggerAdapter, self).isEnabledFor(level)


def _ensure_unicode(msg):
    """Do our best to turn the input argument into a unicode object.
    """
    if not isinstance(msg, six.text_type):
        if isinstance(msg, six.binary_type):
            msg = encodeutils.safe_decode(
                msg,
                incoming='utf-8',
                errors='xmlcharrefreplace',
            )
        else:
            msg = six.text_type(msg)
    return msg


class KeywordArgumentAdapter(BaseLoggerAdapter):
    """Logger adapter to add keyword arguments to log record's extra data

    Keywords passed to the log call are added to the "extra"
    dictionary passed to the underlying logger so they are emitted
    with the log message and available to the format string.

    Special keywords:

    extra
      An existing dictionary of extra values to be passed to the
      logger. If present, the dictionary is copied and extended.
    resource
      A dictionary-like object containing a ``name`` key or ``type``
       and ``id`` keys.

    """

    def process(self, msg, kwargs):
        msg = _ensure_unicode(msg)
        # Make a new extra dictionary combining the values we were
        # given when we were constructed and anything from kwargs.
        extra = {}
        extra.update(self.extra)
        if 'extra' in kwargs:
            extra.update(kwargs.pop('extra'))
        # Move any unknown keyword arguments into the extra
        # dictionary.
        for name in list(kwargs.keys()):
            if name == 'exc_info':
                continue
            extra[name] = kwargs.pop(name)
        # NOTE(dhellmann): The gap between when the adapter is called
        # and when the formatter needs to know what the extra values
        # are is large enough that we can't get back to the original
        # extra dictionary easily. We leave a hint to ourselves here
        # in the form of a list of keys, which will eventually be
        # attributes of the LogRecord processed by the formatter. That
        # allows the formatter to know which values were original and
        # which were extra, so it can treat them differently (see
        # JSONFormatter for an example of this). We sort the keys so
        # it is possible to write sane unit tests.
        extra['extra_keys'] = list(sorted(extra.keys()))
        # Place the updated extra values back into the keyword
        # arguments.
        kwargs['extra'] = extra

        # NOTE(jdg): We would like an easy way to add resource info
        # to logging, for example a header like 'volume-<uuid>'
        # Turns out Nova implemented this but it's Nova specific with
        # instance.  Also there's resource_uuid that's been added to
        # context, but again that only works for Instances, and it
        # only works for contexts that have the resource id set.
        resource = kwargs['extra'].get('resource', None)
        if resource:

            # Many OpenStack resources have a name entry in their db ref
            # of the form <resource_type>-<uuid>, let's just use that if
            # it's passed in
            if not resource.get('name', None):

                # For resources that don't have the name of the format we wish
                # to use (or places where the LOG call may not have the full
                # object ref, allow them to pass in a dict:
                # resource={'type': volume, 'id': uuid}

                resource_type = resource.get('type', None)
                resource_id = resource.get('id', None)

                if resource_type and resource_id:
                    kwargs['extra']['resource'] = ('[' + resource_type +
                                                   '-' + resource_id + '] ')
            else:
                # FIXME(jdg): Since the name format can be specified via conf
                # entry, we may want to consider allowing this to be configured
                # here as well
                kwargs['extra']['resource'] = ('[' + resource.get('name', '')
                                               + '] ')

        return msg, kwargs


def _create_logging_excepthook(product_name):
    def logging_excepthook(exc_type, value, tb):
        extra = {'exc_info': (exc_type, value, tb)}
        getLogger(product_name).critical(
            "".join(traceback.format_exception_only(exc_type, value)),
            **extra)
    return logging_excepthook


class LogConfigError(Exception):

    message = _('Error loading logging config %(log_config)s: %(err_msg)s')

    def __init__(self, log_config, err_msg):
        self.log_config = log_config
        self.err_msg = err_msg

    def __str__(self):
        return self.message % dict(log_config=self.log_config,
                                   err_msg=self.err_msg)


def _load_log_config(log_config_append):
    try:
        logging.config.fileConfig(log_config_append,
                                  disable_existing_loggers=False)
    except (moves.configparser.Error, KeyError) as exc:
        raise LogConfigError(log_config_append, six.text_type(exc))


def register_options(conf):
    """Register the command line and configuration options used by oslo.log."""
    conf.register_cli_opts(_options.common_cli_opts)
    conf.register_cli_opts(_options.logging_cli_opts)
    conf.register_opts(_options.generic_log_opts)
    conf.register_opts(_options.log_opts)
    formatters._store_global_conf(conf)


def setup(conf, product_name, version='unknown'):
    """Setup logging for the current application."""
    if conf.log_config_append:
        _load_log_config(conf.log_config_append)
    else:
        _setup_logging_from_conf(conf, product_name, version)
    sys.excepthook = _create_logging_excepthook(product_name)


def set_defaults(logging_context_format_string=None,
                 default_log_levels=None):
    """Set default values for the configuration options used by oslo.log."""
    # Just in case the caller is not setting the
    # default_log_level. This is insurance because
    # we introduced the default_log_level parameter
    # later in a backwards in-compatible change
    if default_log_levels is not None:
        cfg.set_defaults(
            _options.log_opts,
            default_log_levels=default_log_levels)
    if logging_context_format_string is not None:
        cfg.set_defaults(
            _options.log_opts,
            logging_context_format_string=logging_context_format_string)


def tempest_set_log_file(filename):
    """Provide an API for tempest to set the logging filename.

    .. warning:: Only Tempest should use this function.

    We don't want applications to set a default log file, so we don't
    want this in set_defaults(). Because tempest doesn't use a
    configuration file we don't have another convenient way to safely
    set the log file default.

    """
    cfg.set_defaults(_options.logging_cli_opts, log_file=filename)


def _find_facility(facility):
    # NOTE(jd): Check the validity of facilities at run time as they differ
    # depending on the OS and Python version being used.
    valid_facilities = [f for f in
                        ["LOG_KERN", "LOG_USER", "LOG_MAIL",
                         "LOG_DAEMON", "LOG_AUTH", "LOG_SYSLOG",
                         "LOG_LPR", "LOG_NEWS", "LOG_UUCP",
                         "LOG_CRON", "LOG_AUTHPRIV", "LOG_FTP",
                         "LOG_LOCAL0", "LOG_LOCAL1", "LOG_LOCAL2",
                         "LOG_LOCAL3", "LOG_LOCAL4", "LOG_LOCAL5",
                         "LOG_LOCAL6", "LOG_LOCAL7"]
                        if getattr(syslog, f, None)]

    facility = facility.upper()

    if not facility.startswith("LOG_"):
        facility = "LOG_" + facility

    if facility not in valid_facilities:
        raise TypeError(_('syslog facility must be one of: %s') %
                        ', '.join("'%s'" % fac
                                  for fac in valid_facilities))

    return getattr(syslog, facility)


def _setup_logging_from_conf(conf, project, version):
    log_root = getLogger(None).logger
    for handler in log_root.handlers:
        log_root.removeHandler(handler)

    logpath = _get_log_file_path(conf)
    if logpath:
        filelog = logging.handlers.WatchedFileHandler(logpath)
        log_root.addHandler(filelog)

    if conf.use_stderr:
        streamlog = handlers.ColorHandler()
        log_root.addHandler(streamlog)

    elif not logpath:
        # pass sys.stdout as a positional argument
        # python2.6 calls the argument strm, in 2.7 it's stream
        streamlog = logging.StreamHandler(sys.stdout)
        log_root.addHandler(streamlog)

    if conf.publish_errors:
        handler = importutils.import_object(
            "oslo.messaging.notify.log_handler.PublishErrorsHandler",
            logging.ERROR)
        log_root.addHandler(handler)

    if conf.use_syslog:
        facility = _find_facility(conf.syslog_log_facility)
        # TODO(bogdando) use the format provided by RFCSysLogHandler after
        # existing syslog format deprecation in J
        syslog = handlers.OSSysLogHandler(
            facility=facility,
            use_syslog_rfc_format=conf.use_syslog_rfc_format)
        log_root.addHandler(syslog)

    datefmt = conf.log_date_format
    for handler in log_root.handlers:
        # NOTE(alaski): CONF.log_format overrides everything currently.  This
        # should be deprecated in favor of context aware formatting.
        if conf.log_format:
            handler.setFormatter(logging.Formatter(fmt=conf.log_format,
                                                   datefmt=datefmt))
            log_root.info('Deprecated: log_format is now deprecated and will '
                          'be removed in the next release')
        else:
            handler.setFormatter(formatters.ContextFormatter(project=project,
                                                             version=version,
                                                             datefmt=datefmt,
                                                             config=conf))

    if conf.debug:
        log_root.setLevel(logging.DEBUG)
    elif conf.verbose:
        log_root.setLevel(logging.INFO)
    else:
        log_root.setLevel(logging.WARNING)

    for pair in conf.default_log_levels:
        mod, _sep, level_name = pair.partition('=')
        logger = logging.getLogger(mod)
        # NOTE(AAzza) in python2.6 Logger.setLevel doesn't convert string name
        # to integer code.
        if sys.version_info < (2, 7):
            level = logging.getLevelName(level_name)
            logger.setLevel(level)
        else:
            logger.setLevel(level_name)

_loggers = {}


def getLogger(name=None, project='unknown', version='unknown'):
    """Build a logger with the given name.

    :param name: The name for the logger. This is usually the module
                 name, ``__name__``.
    :type name: string
    :param project: The name of the project, to be injected into log
                    messages. For example, ``'nova'``.
    :type project: string
    :param version: The version of the project, to be injected into log
                    messages. For example, ``'2014.2'``.
    :type version: string
    """
    if name not in _loggers:
        _loggers[name] = KeywordArgumentAdapter(logging.getLogger(name),
                                                {'project': project,
                                                 'version': version})
    return _loggers[name]
