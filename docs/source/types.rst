Types
=====

.. automodule:: smartconfig.types

Configurations
--------------

.. class:: ConfigurationDict

   A dictionary in the configuration. Its keys are strings and its values are
   configurations.

   Type alias for ``Dict[str, Union[Configuration]]``

.. class:: ConfigurationList

   A list in the configuration.

   Type alias for ``List[Union[Configuration]]``

.. class:: ConfigurationContainer

   A container; an internal node in the configuration tree.

   Type alias for ``Union[ConfigurationDict, ConfigurationList]``

.. class:: ConfigurationValue

   A "simple value"; a leaf in the configuration tree.

   Type alias for ``Union[str, int, float, bool, datetime.datetime, datetime.date, None]``

.. class:: Configuration

   Any type of configuration. Could be a container or a simple value.

   Type alias for ``Union[ConfigurationContainer, ConfigurationValue]``


Unresolved Containers
---------------------

.. autoclass:: UnresolvedDict
   :members:
   :undoc-members:

   .. automethod:: __len__
   .. automethod:: __getitem__
   .. automethod:: __iter__

.. autoclass:: UnresolvedList
   :members:
   :undoc-members:

   .. automethod:: __len__
   .. automethod:: __getitem__
   .. automethod:: __iter__

.. autoclass:: UnresolvedFunctionCall
   :members:
   :undoc-members:

   .. automethod:: __getitem__

Functions
---------

.. autoclass:: Function
   :members:
   :undoc-members:

   .. automethod:: new
   .. automethod:: __call__

.. autoclass:: FunctionArgs
   :members:
   :undoc-members:

Special Strings
----------------

.. autoclass:: RawString

.. autoclass:: RecursiveString

Miscellaneous
-------------

.. class:: Schema

   Type alias for ``Mapping[str, Any]``.


.. class:: KeyPath

   Type alias for ``Tuple[str, ...]``. This represents a path of keys leading to a
   particular piece of a nested configuration.

.. class:: FunctionCallChecker

   This is the signature of the function that :func:`resolve` uses to check for function
   calls. This should accept two arguments: the :class:`ConfigurationDict` representing
   a possible function call, and a mapping of function names to available functions as
   :class:`Function` instances. If the dictionary represents a valid function call,
   this should return the :class:`Function` and a :class:`Configuration` representing
   its input. Otherwise, it should return None. If the functionc call is invalid and
   malformed, this should raise a :class:`ValueError`.


   Type alias for:

   .. code:: python

      Callable[
            [ConfigurationDict, Mapping[str, Function]],
            Union[tuple[Function, Configuration], None],
      ]


.. autoclass:: ResolutionContext
