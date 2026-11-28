smartconfig
===========

`smartconfig` is a Python library for enhancing standard configuration formats
(JSON, YAML, TOML) with dynamic features like interpolation, type conversion,
and function evaluation, allowing you to build powerful configuration systems for your
applications.

.. testsetup:: intro

    from pprint import pprint as print

.. testcode:: intro

    import smartconfig

    # 1) load or define a "raw" configuration. In the example config below, the
    # "welcome" string contains a placeholder that should be interpolated.
    config = {
        "course": "DSC 10",
        "start": "2025-09-01",
        "welcome": "Welcome to ${course}!",
    }

    # 2) define a schema that specifies the expected structure of the config
    schema = {
        "type": "dict",
        "required_keys": {
            "course": {"type": "string"},
            "start": {"type": "date"},
            "welcome": {"type": "string"},
        },
    }

    # 3) "resolve" the configuration
    print(smartconfig.resolve(config, schema))

This results in:

.. testoutput:: intro

    {'course': 'DSC 10',
     'start': datetime.date(2025, 9, 1),
     'welcome': 'Welcome to DSC 10!'}

For a more detailed introduction, see :doc:`Features and Quick Start <quick_start>`.
For the whole configuration language on one page, see the :doc:`cheatsheet`, which
is also installed with the package for AI agents to read (it includes a snippet
to paste into a project's ``CLAUDE.md`` or ``AGENTS.md``).

Installation
------------

Install directly from GitHub using `uv <https://docs.astral.sh/uv/>`_:

.. code:: bash

    uv add git+https://github.com/eldridgejm/smartconfig.git

Or with pip:

.. code:: bash

    pip install git+https://github.com/eldridgejm/smartconfig.git

Table of Contents
-----------------

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   quick_start

.. toctree::
   :maxdepth: 1
   :caption: Key Concepts

   configurations
   schemas
   prototypes
   resolution

.. toctree::
   :maxdepth: 1
   :caption: Default Behavior

   default_converters
   default_functions

.. toctree::
   :maxdepth: 1
   :caption: Customizing Behavior

   resolution_in_detail
   custom_converters
   custom_functions
   inline_python
   custom_filters
   external_variables
   type_preservation

.. toctree::
   :maxdepth: 1
   :caption: Reference

   cheatsheet
   api
   types
   converters
   exceptions

.. toctree::
   :maxdepth: 1
   :caption: Recipes

   recipes
