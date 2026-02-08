.. _prototypes:

Prototypes
==========


Prototypes provide a class-based way to describe configuration structure using
Python type hints. Instead of writing a schema dictionary, you subclass
``smartconfig.Prototype`` and annotate its attributes; passing that class to
:func:`smartconfig.resolve` returns an instance of your prototype. See
:doc:`schemas` for more examples and information on how to define prototypes.

.. currentmodule:: smartconfig

.. autoclass:: Prototype
   :members: _schema, _as_dict, _from_dict
   :undoc-members:

.. autoclass:: NotRequired

.. autofunction:: is_prototype_class
