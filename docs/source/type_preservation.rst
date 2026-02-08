.. _type-preservation:

Type Preservation
=================

Typically, the input to :func:`smartconfig.resolve` will be a plain Python object (e.g., a ``dict``
or a ``list``). Sometimes, however, it may be another mapping type that behaves like a
``dict``, but has some additional functionality. One example is the `ruamel` package which
is capable of round-tripping yaml, comments and all. To accomplish this, ruamel produces
a dict-like object which stores the comments internally. If we resolve this dict-like
object with :code:`preserve_type = False`, then we'll lose these comments; therefore, we
should use :code:`preserve_type = True`.

At present, type preservation is done by constructing the resolved output as
normal, but then making a deep copy of `cfg` and recursively copying each leaf
value into this deep copy. Therefore, there is a performance cost.
