.. _type-preservation:

Type Preservation
=================

Typically, the input to :func:`smartconfig.resolve` will be a plain Python object (e.g., a ``dict``
or a ``list``). Sometimes, however, it may be a subclass of ``dict`` or ``list`` with
some additional functionality (such as ruamel's ``CommentedMap`` and ``CommentedSeq``).
Other mapping types aren't treated as containers. One example is the `ruamel` package which
is capable of round-tripping yaml, comments and all. To accomplish this, ruamel produces
a dict-like object which stores the comments internally. If we resolve this dict-like
object with :code:`preserve_type = False`, then we'll lose these comments; therefore, we
should use :code:`preserve_type = True`.

At present, type preservation is done by constructing the resolved output as
normal, but then making a deep copy of `cfg` and recursively copying the resolved
values into this deep copy. Therefore, there is a performance cost.

Only containers that appear in `cfg` are preserved. Where `cfg` has a function
call, nothing there is preserved: the function's result is resolved into plain
dicts and lists. Keys filled in by defaults are added to the preserved
container.
