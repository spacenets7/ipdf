# Preserved LazyDigest module

The original digest pipeline, routes, UI, source adapters, scripts and tests were
moved here during the iPDF pivot. They are retained as reference/source for future
optional modules, and are not mounted or collected by the active iPDF app/tests.

The shared `app.llm`, `app.extract`, `app.db` and `app.audio` have evolved for iPDF.
Re-enabling these archived routes requires updating their imports and adapting
their shared-service calls. The supported application is `app.main:app`.
