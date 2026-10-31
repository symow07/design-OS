"""Shared boundary only; bottle and assembly compilers remain separate."""


def backend(task):
    return (getattr(task, 'options', None) or {}).get('authoring_backend')


def is_authored(task):
    return backend(task) in ('hybrid_bottle','hybrid_assembly')


#: the authoring pages (stand-master/, serum-master/) retired with the Day 4–6 masters on 2026-10-29
RETIRED_PAGE = ('This authored master\'s page is retired (the history pages, the owner\'s goal of 2026-10-29); its '
                'checked revisions stay in its media folder.')
