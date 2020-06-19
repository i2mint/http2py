def add_defaults(d, dflts):
    """Adds defaults to every (mapping) value of every item of d"""
    dflt_keys = set(dflts)
    for k, v in d.items():
        d[k].update({dflt_key: dflts[dflt_key] for dflt_key in dflt_keys.difference(v)})
    return d
