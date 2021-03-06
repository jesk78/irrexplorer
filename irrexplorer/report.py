#!/usr/bin/env python
# Copyright (c) 2015, Job Snijders
# Copyright (c) 2015, NORDUnet A/S
#
# This file is part of IRR Explorer
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import time


SOURCE = 'source'
RIPE = 'ripe'
BGP = 'bgp'

# IRR_DBS = ['afrinic', 'altdb', 'apnic', 'arin', 'bboi', 'bell', 'gt', 'jpirr', 'level3', 'nttcom', 'radb', 'rgnet', 'savvis', 'tc', 'ripe']


class NoPrefixError(Exception):
    pass



def add_prefix_advice(prefixes):

    # default, primary, succes, info, warning, danger
    for pfx, pfx_data in prefixes.items():
        print 'Prefix: %s, data: %s' % (pfx, pfx_data)
        pfx_source = pfx_data[SOURCE]

        anywhere = set()
        for entries in pfx_source.values():
            for entry in entries:
                anywhere.add(entry)
        anywhere = list(anywhere)

        anywhere_not_ripe = set()
        for db, entries in pfx_source.items():
            if db != RIPE:
                for entry in entries:
                    anywhere_not_ripe.add(entry)
        anywhere_not_ripe = list(anywhere_not_ripe)

        #print '  IRR orgins:', anywhere
        #print '  IRR orgins % ripe:', anywhere_not_ripe

        if not BGP in pfx_data:
            bgp_origin = None
        else:
            # afaict this should never happen, at least not as long as we only have a single table
            if len(pfx_data[BGP]) > 2:
                print 'Multiple BGP sources:', pfx_data[BGP], 'only using first origin'
            bgp_origin = list(pfx_data[BGP])[0]

        # check if this is rfc managed space
        managed = False

        for source in pfx_data:
            if source.endswith('_managed') and source.lower() != 'ripe_managed':
                rfc_source = source.rsplit('_',1)[0]
                pfx_data['advice'] = "Prefix is %s space.  Drunk engineer." % rfc_source
                pfx_data['label'] = "warning"
                managed = True
                break

        if managed:
            continue # don't bother checking anything else

        if 'ripe_managed' in pfx_data:

            if 'ripe' in pfx_source:

                if bgp_origin and bgp_origin in pfx_source['ripe']:

                    if len(anywhere) == 1: # only ripe as origin
                        pfx_data['advice'] = "Perfect"
                        pfx_data['label'] = "success"

                    elif [bgp_origin] == anywhere:
                        pfx_data['advice'] = "Proper RIPE DB object, but foreign objects also exist, consider remoing these."
                        pfx_data['label'] = "warning"

                    elif anywhere_not_ripe:
                        pfx_data['advice'] = "Proper RIPE DB object, but foreign objects also exist, consider removing these. BGP origin does not match all IRR entries."
                        pfx_data['label'] = "danger"

                    elif len(anywhere) > 1:
                        pfx_data['advice'] = "Multiple entries exists in RIPE DB, with different origin. Consider removing conflicting entries."
                        pfx_data['label'] = "warning"

                    else:
                        pfx_data['advice'] = "Looks good, but multiple entries exists in RIPE DB"
                        pfx_data['label'] = "success"

                elif bgp_origin and pfx_source:
                    pfx_data['advice'] = "Prefix is in DFZ, but registered with wrong origin in RIPE!"
                    pfx_data['label'] = "danger"

                else: # no bgp origin
                    # same as last else clause, not sure if this could be made a bit better
                    if ':' in pfx:
                        pfx_data['advice'] = "Look like network is not announcing registered v6 prefix yet"
                    else:
                        pfx_data['advice'] = "Not seen in BGP, but (legacy?) route-objects exist, consider clean-up"
                    pfx_data['label'] = "info"

            else:   # no ripe registration

                if bgp_origin:
                    # do if on as match
                    if anywhere: # could use anywhere_but_ripe - result would be the same
                        if [bgp_origin] == anywhere:
                            pfx_data['advice'] = "Prefix is in DFZ and has an IRR record, but NOT in RIPE! BGP origin matches IRR entries."
                            pfx_data['label'] = "warning"
                        else:
                            pfx_data['advice'] = "Prefix is in DFZ and has an IRR record, but NOT in RIPE! BGP origin does not match all IRR entries."
                            pfx_data['label'] = "danger"
                    else:
                        pfx_data['advice'] = "Prefix is in DFZ, but NOT registered in any IRR and should go into RIPE!"
                        pfx_data['label'] = "danger"

                else:
                    pfx_data['advice'] = "Route objects in foreign registries exist, but no BGP origin. Consider moving IRR object to RIPE DB or deleting them."
                    pfx_data['label'] = "warning"

        elif bgp_origin: # not ripe managed, but have bgp_origin

            if bgp_origin in anywhere:

                if len(anywhere) == 1:
                    pfx_data['advice'] = "Looks good: BGP origin consistent with AS in route-objects"
                    pfx_data['label'] = "success"
                else:
                    pfx_data['advice'] = "Multiple route-object exist with different origins"
                    pfx_data['label'] = 'warning'

            else:
                pfx_data['advice'] = "Prefix in DFZ, but no route-object with correct origin anywhere"
                pfx_data['label'] = "danger"

        else: # not ripe managed, no bgp origin
            if ':' in pfx:
                pfx_data['advice'] = "Look like network is not announcing registered v6 prefix yet"
            else:
                pfx_data['advice'] = "Not seen in BGP, but (legacy?) route-objects exist, consider clean-up"
            pfx_data['label'] = "info"


    return prefixes



def prefix(pgdb, prefix):
    """
        - find least specific
        - search in BGP for more specifics
        - search in IRR for more specifics
        - check all prefixes whether they are RIPE managed or not
        - return dict
    """

    t_start = time.time()

    print 'Prefix report: %s' % (prefix,)

    routes = pgdb.query_prefix(prefix)

    prefixes = _build_prefix_dict(routes)

    # avoid spamming log too much
    if len(prefixes) < 20:
        print 'Prefixes:', prefixes.keys()
    else:
        print 'Prefixes: <%i>' % len(prefixes)

    # TODO if we find any prefixes larger than the inputted one, we should find prefixes covered by that prefixes
    # Go through the prefixes, find the shortest one, if it is different from the inputted one, do another search

    add_prefix_advice(prefixes)

    print 'Advice:'
    for p,d in prefixes.items():
        print '%s: %s' % (p,d['advice'])

    # Move source out into top dict, to fit with the datatables stuff
    for pfx_data in prefixes.values():
        pfx_data.update(pfx_data.pop(SOURCE))

    t_delta = time.time() - t_start
    print 'Time for prefix report for %s: %s\n' % (prefix, round(t_delta,2))

    return prefixes



def _build_prefix_dict(db_result):

    result = {}

    for route, asn, source, managed in db_result:
        #print 'BDP', route, asn, source, managed
        ps = result.setdefault(route, {}).setdefault(SOURCE, {})
        if not asn in ps.get(source, []): # we can get duplicates due to htj's sql limitations
            ps.setdefault(source, []).append(asn)
        if managed:
            result[route][managed] = True

    # move bgp out from sources and into top-level dict for the prefix
    for data in result.values():
        if BGP in data[SOURCE]:
            data[BGP] = data[SOURCE].pop(BGP)

    return result



def as_prefixes(pgdb, as_number):

    if not type(as_number) is int:
        raise ValueError('Invalid argument provided for as number')

    print 'AS Prefix Report: ', as_number

    t_start = time.time()

    prefixes = pgdb.query_as(as_number)

    # do deep as query if prefix set is sufficiently small to do it fast
    # we could probably go to ~1000 here
    if len(prefixes) < 1000:
        print 'Performing deep query for AS', as_number
        prefixes = pgdb.query_as_deep(as_number)

    result = _build_prefix_dict(prefixes)

    add_prefix_advice(result)

    print 'Advice:'
    for p,d in result.items():
        print '%s: %s' % (p,d['advice'])

    # OK, this is not how i want to do things, but I cannot figure out the javascript stuff
    for pfx_data in result.values():
        pfx_data.update(pfx_data.pop(SOURCE))

    t_delta = time.time() - t_start
    print 'Time for AS prefixes for %s: %s' % (as_number, round(t_delta,2))
    print

    return result



def macro_expand(pgdb, as_macro):

    print 'Macro Expand Report:', as_macro

    t_start = time.time()

    macros = pgdb.query_as_macro_expand(as_macro)

    result = []
    for macro, source, depth, path, members in macros:
        e = { 'as_macro' : macro,
              'source'   : source,
              'depth'    : depth,
              'path'     : path,
              'members'  : members
        }
        result.append(e)

    t_delta = time.time() - t_start
    print 'Time for macro expand report for %s: %s' % (as_macro, round(t_delta,2))
    print

    return result



def macro_contain(pgdb, as_object):

    print 'Macro Contains Report:', as_object

    t_start = time.time()

    macros = pgdb.query_as_contain(as_object)

    result = {}
    for macro, source in macros:
        result.setdefault(macro, {})[source] = True

    t_delta = time.time() - t_start

    print 'Time for as contains report for %s: %s' % (as_object, round(t_delta,2))
    print

    return result

