import subprocess
import mimetypes
import tempfile
import datetime
import os.path
import shutil

import pyx

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse, Http404

from kn.base.conf import from_settings_import
from_settings_import("DT_MIN", "DT_MAX", globals())
from django.conf import settings

import kn.leden.entities as Es

@login_required
def view(request, graph, ext):
    if not graph in GRAPHS:
        raise Http404
    timeout, update, exts = GRAPHS[graph]
    if not ext in exts:
        raise Http404
    graph_fn = graph + '.' + ext
    path = os.path.join(settings.GRAPHS_PATH, graph_fn)
    # Check if we should update the graph
    if (not default_storage.exists(path) or
            datetime.datetime.now() - default_storage.created_time(path) 
                > datetime.timedelta(seconds=timeout)):
        update(default_storage.path(
                    os.path.join(settings.GRAPHS_PATH, graph + '.')))
    return HttpResponse(FileWrapper(default_storage.open(path)),
                                content_type=mimetypes.guess_type(path))

def update_member_count(base_path):
    ret = _generate_member_count()
    if len(ret) < 3:
        ret = list(enumerate(range(3)))
    g = pyx.graph.graphxy(width=20, x=pyx.graph.axis.linear(min=1,
                    painter=pyx.graph.axis.painter.regular(
                            gridattrs=[pyx.attr.changelist([
                                pyx.color.gray(0.8)])])))
    g.plot(pyx.graph.data.points(ret,x=1,y=2),
                [pyx.graph.style.symbol(size=0.03,
                        symbol=pyx.graph.style.symbol.plus)])
    # TODO split into separate helper
    # work-around for PyX trying to write in the current directory
    old_wd = os.getcwd()
    temp_dir = tempfile.mkdtemp()
    try:
        os.chdir(temp_dir)
        # Write PDF.  Prevent its call to f.close().
        g.writePDFfile('graph')
        subprocess.call(['convert', '-density', '300', 'graph.pdf',
                            '-resize', '1600x', 'graph.png'])
        shutil.move('graph.pdf', base_path + 'pdf')
        shutil.move('graph.png', base_path + 'png')
    finally:
        os.chdir(old_wd)
        shutil.rmtree(temp_dir)

def _generate_member_count():
    events = []
    for rel in Es.query_relations(_with=Es.id_by_name('leden'), how=None):
        events.append((max(rel['from'], Es.DT_MIN), True))
        if rel['until'] != Es.DT_MAX:
            events.append((rel['until'], False))
    N = 0
    old_days = -1
    old_N = None
    ret = []
    for when, what in sorted(events, key=lambda x: x[0]):
        N += 1 if what else -1
        days = (when - Es.DT_MIN).days
        if old_days != days:
            if old_N:
                ret.append([old_days, old_N])
            old_days = days
            old_N = N
    ret.append([days, N])
    ret = [(1 + days / 365.242, N) for days, N in ret]
    return ret

GRAPHS = {
        # <name>:       (seconds_to_cache, update_functions, extensions)
        'member-count': (60*60, update_member_count, ('png', 'pdf'))
        }

# vim: et:sta:bs=2:sw=4:
