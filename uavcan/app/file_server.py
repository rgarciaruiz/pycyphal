#
# Copyright (C) 2014-2015  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Ben Dyer <ben_dyer@mac.com>
#         Pavel Kirienko <pavel.kirienko@zubax.com>
#

from __future__ import division, absolute_import, print_function, unicode_literals
import os
from logging import getLogger
import uavcan
import errno


logger = getLogger(__name__)


def _try_resolve_relative_path(search_in, rel_path):
    rel_path = os.path.normcase(os.path.normpath(rel_path))
    for p in search_in:
        p = os.path.normcase(os.path.abspath(p))
        if p.endswith(rel_path) and os.path.isfile(p):
            return p
        joined = os.path.join(p, rel_path)
        if os.path.isfile(joined):
            return joined


# noinspection PyBroadException
class FileServer(object):
    def __init__(self, node, search_pathes=None):
        self.search_pathes = search_pathes or []
        self._handles = []

        def add_handler(datatype, callback):
            self._handles.append(node.add_handler(datatype, callback))

        add_handler(uavcan.protocol.file.GetInfo, self._get_info)
        add_handler(uavcan.protocol.file.Read, self._read)
        # TODO: support all file services

    def close(self):
        for x in self._handles:
            x.close()

    def _resolve_path(self, relative):
        rel = relative.path.decode().replace(relative.SEPARATOR, os.path.sep)
        out = _try_resolve_relative_path(self.search_pathes, rel)
        if not out:
            raise OSError(errno.ENOENT)
        return out

    def _get_info(self, e):
        logger.debug("[#{0:03d}:uavcan.protocol.file.GetInfo] {1!r}"
                     .format(e.transfer.source_node_id, e.request.path.path.decode()))
        try:
            with open(self._resolve_path(e.request.path), "rb") as f:
                data = f.read()
                resp = uavcan.protocol.file.GetInfo.Response()
                resp.error.value = resp.error.OK
                resp.size = len(data)
                resp.entry_type.flags = resp.entry_type.FLAG_FILE | resp.entry_type.FLAG_READABLE
        except Exception:
            # TODO: Convert OSError codes to the error codes defined in DSDL
            logger.exception("[#{0:03d}:uavcan.protocol.file.GetInfo] error", exc_info=True)
            resp = uavcan.protocol.file.GetInfo.Response()
            resp.error.value = resp.error.UNKNOWN_ERROR

        return resp

    def _read(self, e):
        logger.debug("[#{0:03d}:uavcan.protocol.file.Read] {1!r} @ offset {2:d}"
                     .format(e.transfer.source_node_id, e.request.path.path.decode(), e.request.offset))
        try:
            with open(self._resolve_path(e.request.path), "rb") as f:
                f.seek(e.request.offset)
                resp = uavcan.protocol.file.Read.Response()
                read_size = uavcan.get_uavcan_data_type(uavcan.get_fields(resp)['data']).max_size
                resp.data = f.read(read_size)
                resp.error.value = resp.error.OK
        except Exception:
            logger.exception("[#{0:03d}:uavcan.protocol.file.Read] error")
            resp = uavcan.protocol.file.Read.Response()
            resp.error.value = resp.error.UNKNOWN_ERROR

        return resp