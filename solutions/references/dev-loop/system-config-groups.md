# System configuration groups

## Rule: cron definitions go under a shared group

All `*_cron_definition` fields live under the shared `cron_definition_settings` group, **not** under each bundle's
own group, so admins find every schedule in one place.

```yaml
# BAD - per-bundle group
system_configuration:
    groups:
        my_bundle_settings:
            title: 'My Bundle Settings'
            configuration:
                fields:
                    - my_bundle.some_cron_definition   # wrong place

# GOOD - shared group
system_configuration:
    groups:
        cron_definition_settings:
            title: 'Cron Schedules'
            configuration:
                fields:
                    - my_bundle.some_cron_definition
                    - other_bundle.other_cron_definition
```

Define the field itself (`some_cron_definition`) under your bundle's `system_configuration/settings.yml` as usual;
only reference it from the shared group's **groups -> fields** list.
