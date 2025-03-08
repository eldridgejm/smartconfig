Built-in Functions
==================

`smartconfig` has the ability to evaluate function calls defined within the
configuration itself (see: :ref:`function-calls`). It comes with several built-in functions that allow for
basic manipulation of the configuration; these are defined in the
:mod:`smartconfig.functions` module. The default functions available to
:func:`smartconfig.resolve` are defined in
:data:`smartconfig.DEFAULT_FUNCTIONS`.

.. module:: smartconfig.functions

The built-in functions are:

.. autosummary::

   concatenate
   dict_from_items
   filter
   if
   let
   loop
   range
   raw
   recursive
   splice
   update
   update_shallow
   zip

.. autofunction:: concatenate

.. function:: raw(args: FunctionArgs)

   Makes a :class:`smartconfig.types.RawString` that will not be interpolated or converted.

   ``args.input`` should be a single string. If not, an error is raised.

.. autofunction:: recursive
.. autofunction:: splice
.. autofunction:: update
.. autofunction:: update_shallow
.. autofunction:: if
.. autofunction:: let
.. autofunction:: loop
.. autofunction:: concatenate
.. autofunction:: zip
.. autofunction:: filter
.. autofunction:: range
.. autofunction:: dict_from_items
