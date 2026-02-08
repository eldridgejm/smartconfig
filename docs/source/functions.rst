Functions
=========

Default functions are organized into **core functions** and **standard library
(stdlib) functions**. Core functions handle control flow, interpolation modes,
and structural operations. Stdlib functions are namespaced and provide list,
dictionary, and datetime operations.

See :doc:`default_functions` for usage examples and details on how to invoke
functions in configurations.

Core Functions
--------------

Core functions are available as top-level names (e.g., ``__if__``, ``__let__``).

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - ``if``
     - Conditional logic: evaluates ``condition``, returns ``then`` or ``else``
   * - ``let``
     - Define local variables and/or references within a subtree
   * - ``raw``
     - Prevent interpolation of ``${...}`` references
   * - ``resolve``
     - Single-pass interpolation (override inherited raw/fully_resolve mode)
   * - ``fully_resolve``
     - Repeated interpolation until the string stabilizes
   * - ``splice``
     - Copy a subtree from elsewhere in the configuration
   * - ``use``
     - Copy a template with optional deep-merge overrides

Standard Library Functions
--------------------------

Stdlib functions use dotted names (e.g., ``__list.loop__``, ``__dict.update__``).

**List Functions** (``smartconfig.stdlib.list``)

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - ``list.concatenate``
     - Concatenate lists
   * - ``list.filter``
     - Filter a list by condition
   * - ``list.loop``
     - Generate a list by iteration
   * - ``list.range``
     - Generate a list of numbers
   * - ``list.zip``
     - Zip lists together

**Dictionary Functions** (``smartconfig.stdlib.dict``)

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - ``dict.from_items``
     - Create a dictionary from key-value pairs
   * - ``dict.update``
     - Deep merge dictionaries
   * - ``dict.update_shallow``
     - Shallow merge dictionaries

**Datetime Functions** (``smartconfig.stdlib.datetime``)

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - ``datetime.at``
     - Combine a date with a time
   * - ``datetime.first``
     - Find the first weekday before/after a date
   * - ``datetime.offset``
     - Offset a date by a given amount
   * - ``datetime.parse``
     - Parse a natural language date/datetime string
