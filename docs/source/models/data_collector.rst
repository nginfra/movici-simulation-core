Data Collector
==============

Configuration Options
~~~~~~~~~~~~~~~~~~~~~

+-------------------+--------+----------------------------------------------------------------+
| Option            | Type   | Description                                                    |
+===================+========+================================================================+
| storage           | string | Set storage to ``"file"`` or ``"sqlite"`` (overrides settings) |
+-------------------+--------+----------------------------------------------------------------+
| database_path     | string | Full path to SQLite database file (if using sqlite storage)    |
+-------------------+--------+----------------------------------------------------------------+
| storage_dir       | string | Results storage location (overrides settings)                  |
+-------------------+--------+----------------------------------------------------------------+
| gather_filter     | object | Subscribe filter for data collection                           |
|                   | /null  |                                                                |
|                   | /"*"   |                                                                |
+-------------------+--------+----------------------------------------------------------------+
| aggregate_updates | bool   | Batch updates per timestamp                                    |
+-------------------+--------+----------------------------------------------------------------+

**Priority**: ``database_path`` > ``storage_dir`` (model config) > ``storage_dir`` (settings)
