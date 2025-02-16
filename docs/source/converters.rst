Built-in Converters
===================

`smartconfig` uses "converters" to transform the values in a configuration file into
Python objects. It comes with several built-in converters that allow for the conversion
of basic types; these are defined in the :mod:`smartconfig.converters` module. The
default converters available to :func:`smartconfig.resolve` are defined in
:data:`smartconfig.DEFAULT_CONVERTERS`.

.. module:: smartconfig.converters

The provided converters are:

.. autosummary::

   arithmetic
   logic
   smartdate
   smartdatetime

.. autofunction:: arithmetic

.. autofunction:: logic

.. autofunction:: smartdate

.. autofunction:: smartdatetime
