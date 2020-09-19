.. publish documentation master file, created by
   sphinx-quickstart on Fri Sep 18 15:52:15 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. automodule:: publish

API
===

Types
-----

we will construct a type hierarchy without inheritance.

at the bottom of the hierarchy are artifact types. we'll create three: one
for unbuilt artifacts, one for built but unpublished artifacts, and another
for published artifacts.

at progressively higher levels are Publications, Collections, and the Universe.
these three types are "internal nodes" of the hierarchy, as they each have children:
a universe contains collections, a collection contains publications, and a publication
contains artifacts. internal nodes will all have the following methods:

  _deep_asdict()
      recursively convert the object to a dictionary

  _children()
      return the children of the internal node

  _replace_children(new_children)
      replace the children of the internal node, returning a new node instance

these methods enable working with internal nodes in a generic way. for instance, we
can write a single publish() function that can accept as input a universe, collection,
publication, or artifact.

.. autoclass:: UnbuiltArtifact
    :members:

.. toctree::
   :maxdepth: 2
   :caption: Contents:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
