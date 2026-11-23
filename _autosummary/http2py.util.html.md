# http2py.util

Small general-purpose helpers: data files, dict defaults, JSON-ability checks.

Also holds the friendly `ModuleNotFoundError` messages used to point a user at
the right install when an optional dependency is missing.

### Functions

| [`add_defaults`](#http2py.util.add_defaults)(d, dflts)   | Adds defaults to every (mapping) value of every item of d   |
|---------------------------------------------------------------------------|-------------------------------------------------------------|
| `is_jsonable`(x)                                                          |                                                             |

### Classes

| `I2mintModuleNotFoundErrorNiceMessage`()   |    |
|--------------------------------------------|----|
| `ModuleNotFoundErrorNiceMessage`()         |    |

### http2py.util.add_defaults(d, dflts)

Adds defaults to every (mapping) value of every item of d
