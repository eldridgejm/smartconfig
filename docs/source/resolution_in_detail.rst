Resolution in Detail
====================

The behavior of :func:`smartconfig.resolve` can be customized in several ways:
you can define custom converters, custom functions, and even change how function
calls are detected. To effectively customize resolution, it helps to understand
how it works under the hood. This page provides a detailed explanation of the
resolution process.

Configuration Graphs
--------------------

When thinking about how resolution works,
it is helpful to conceptualize a configuration as a graph. Each node in the
graph represents a piece of the configuration. We can imagine four different
types of node: dictionary, list, value, and function call. Each edge in the
graph represents a dependency between nodes.

For example, consider the following configuration:

.. code:: python

   {
        "course_name": "Introduction to Python",
        "date_of_first_lecture": "2025-01-10",
        "date_of_first_discussion": "7 days after ${date_of_first_lecture}",
        "message": [
            "Welcome to ${course_name}!",
            "The first lecture is on ${date_of_first_lecture}.",
            "The first discussion is on ${date_of_first_discussion}."
        ],
   }

The graph for this configuration looks like this:

.. mermaid::

   %%{init: {'themeVariables': {'edgeLabelBackground':'rgba(0,0,0,0)'}}}%%
   flowchart TB
       root["root (dict)"]
       course_name["course_name<br/>(value)"]
       date_of_first_lecture["date_of_first_lecture<br/>(value)"]
       date_of_first_discussion["date_of_first_discussion<br/>(value)"]
       message["message (list)"]
       msg0["[0] (value)"]
       msg1["[1] (value)"]
       msg2["[2] (value)"]

       root --> course_name
       root --> date_of_first_lecture
       root --> date_of_first_discussion
       root --> message
       message --> msg0
       message --> msg1
       message --> msg2

       date_of_first_discussion -.->|depends on| date_of_first_lecture
       msg0 -.->|depends on| course_name
       msg1 -.->|depends on| date_of_first_lecture
       msg2 -.->|depends on| date_of_first_discussion

       style root fill:#9370db40,stroke:#9370db
       style message fill:#9370db40,stroke:#9370db
       style course_name fill:#ffd70040,stroke:#ffd700
       style date_of_first_lecture fill:#ffd70040,stroke:#ffd700
       style date_of_first_discussion fill:#ffd70040,stroke:#ffd700
       style msg0 fill:#ffd70040,stroke:#ffd700
       style msg1 fill:#ffd70040,stroke:#ffd700
       style msg2 fill:#ffd70040,stroke:#ffd700

Purple boxes represent containers (dictionary and list nodes), while gold
boxes represent leaf nodes (value nodes).
Solid arrows represent parent-child (containment) relationships.
Dashed arrows represent dependencies introduced by string
interpolation references like ``${course_name}``.

To build the graph representing this configuration, we started by making a
tree. For this configuration, the root of the tree represents the outermost
dictionary. This root has four children: the nodes representing
``course_name``, ``date_of_first_lecture``, ``date_of_first_discussion``, and
``message``. The first three of these children are leaf nodes, as they are
simple values. The ``message`` node represents a list, and it has three
children: the nodes representing the three strings in the list.

On one hand, the edges in this tree represent inclusion relationships. At the
same time, they also represent dependencies. For example, in order to resolve the
outermost dictionary, we must first resolve each of its children. As-is, the tree
does not capture *all* of the dependencies in the configuration; for example, the
value of ``date_of_first_discussion`` depends on the value of
``date_of_first_lecture``. We can represent this dependency by adding a dashed edge
from the node representing ``date_of_first_discussion`` to the node representing
``date_of_first_lecture``, as well as similar edges for the other interpolations,
resulting in a graph that we might call the "configuration graph".

Ideally, this graph is a Directed Acyclic Graph (DAG). If there are cycles in
the graph, it indicates circular dependencies in the configuration, which will
cause resolution to fail.

Resolution Process as a Graph Traversal
---------------------------------------

When a configuration is resolved, a depth-first search is performed on its
configuration graph, starting at the root node. When a dictionary or list node is
encountered, each child is recursively resolved.

When a leaf (value) node is encountered, resolution happens in two phases:

1. **Interpolation**: If the value is a string, any ``${...}`` references are
   expanded using the Jinja2 templating engine.
2. **Conversion**: The interpolated value is passed to a converter function that
   transforms it into the appropriate Python type (e.g., parsing ``"2025-01-10"``
   into a ``datetime.date`` object).

The following sections describe each phase in more detail.

Interpolation and Variable Lookup
---------------------------------

.. module:: smartconfig

During interpolation, references like ``${foo.bar.baz}`` are resolved by looking
up variables. Jinja2 traverses the dotted path by first looking up ``foo``, then
looking up ``bar`` within that result, and finally ``baz``. The variable lookup
follows a specific search order:

1. **Local variables** are searched first. These are variables that exist only
   within certain subtrees of the configuration and are introduced by functions
   like :ref:`func-let` and :ref:`func-loop`. For example, in a loop, the loop
   variable (e.g., ``i``) is a local variable available only within the loop body.

2. **The configuration itself** is searched next. This is how cross-references
   between different parts of the configuration work. When you write
   ``${course_name}``, `smartconfig` looks for a key called ``course_name`` in the
   configuration.

3. **Global variables** are searched last. These are variables passed to
   :func:`resolve` via the ``global_variables`` parameter. Unlike configuration
   values, global variables are not interpolated or converted—they are used as-is.
   This makes them useful for injecting Python functions or constants that should
   be available during interpolation.

Unresolved Configurations and Lazy Resolution
---------------------------------------------

A key insight is that when Jinja2 looks up a reference like ``${course_name}``,
the referenced value might not yet be resolved. To handle this, `smartconfig` wraps
the configuration in special "unresolved" container types:

- :class:`types.UnresolvedDict` wraps dictionaries
- :class:`types.UnresolvedList` wraps lists
- :class:`types.UnresolvedFunctionCall` wraps function call nodes

These unresolved containers behave like their resolved counterparts (you can
access keys, iterate over elements, etc.), but with one crucial difference: when
you access a leaf value, the container automatically triggers resolution of that
value *on demand*.

For example, consider the reference ``${foo.bar.baz}``:

1. Jinja2 looks up ``foo`` and receives an :class:`types.UnresolvedDict`.
2. Jinja2 looks up ``bar`` within that dict and receives another
   :class:`types.UnresolvedDict`.
3. Jinja2 looks up ``baz``, which is a leaf value. At this point, the unresolved
   container recognizes that a value (not another container) is being accessed,
   and it triggers resolution of that value—interpolating and converting it as
   needed.
4. The resolved value is returned to Jinja2 and substituted into the string.

This lazy resolution mechanism is what allows references to work regardless of
the order in which keys appear in the configuration. A value is resolved only
when it is actually needed, and once resolved, the result is cached so that
subsequent accesses return the same value without re-resolving.

Circular Dependency Detection
-----------------------------

Because resolution happens lazily and on-demand, it's possible for circular
dependencies to arise. For example:

.. code:: python

   {
       "a": "${b}",
       "b": "${a}"
   }

Here, resolving ``a`` requires resolving ``b``, but resolving ``b`` requires
resolving ``a``—a circular dependency. Smartconfig detects this by tracking which
nodes are currently "in progress." If a node that is already being resolved is
encountered again, a :class:`exceptions.ResolutionError` is raised with a message
indicating the circular dependency.

Type Conversion
---------------

Once a value has been interpolated (if it was a string), it is passed to a
converter function. The converter's job is to transform the value into the
appropriate Python type as specified by the schema.

Converters are flexible: they accept values of any type and return the converted
result. If the input is a string, the converter typically parses it. For example,
:func:`converters.smartdate` can parse strings like ``"2025-01-10"`` or even
natural language expressions like ``"7 days after 2025-01-10"`` into
``datetime.date`` objects.

If the input is already the correct type (e.g., an integer where an integer is
expected), the converter may simply return it unchanged. This allows configurations
to mix literal values with string expressions that need parsing.

If conversion fails (e.g., the string cannot be parsed as a date), the converter
raises a :class:`exceptions.ConversionError`, which `smartconfig` wraps with
context about where in the configuration the error occurred.
