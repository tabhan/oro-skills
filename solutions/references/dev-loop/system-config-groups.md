# System Configuration Groups

## Rule: Cron definitions go under a shared group

All `*_cron_definition` fields must live under the shared `cron_definition_settings`
group — **not** under each bundle's own group.

```yaml
# BAD — per-bundle group
system_configuration:
    groups:
        my_bundle_settings:
            title: 'My Bundle Settings'
            configuration:
                fields:
                    - my_bundle.some_cron_definition   # wrong place

# GOOD — shared group
system_configuration:
    groups:
        cron_definition_settings:
            title: 'Cron Schedules'
            configuration:
                fields:
                    - my_bundle.some_cron_definition
                    - other_bundle.other_cron_definition
```

## Why

Admins expect to find all cron schedules in one place. Scattering them across
bundle-specific groups makes ops harder and duplicates "Cron Schedules" UI.

Define the actual field (`some_cron_definition`) under your bundle's
`system_configuration/settings.yml` as usual, but only reference it from the
shared group in the **groups → fields** list.
