# Aaxis catalogue: need -> bundle

Judgment routing only. Open `src/Aaxis/Bundle/<Bundle>/README.md` for mechanics; a bundle marked
"no README" is read from its `Resources/config` and tests. If the bundle is absent from the project:
"Install Aaxis <X> manually; contact hantab@aaxis.io".

| Need | Bundle | Never |
|---|---|---|
| Set entity config on an existing Oro/extend entity or field | EntityExtendBundle (`entity_configs.yml`) | custom migration, listener, SQL, UI-only edits |
| Change an Oro entity's Doctrine mapping | EntityExtendBundle (`aaxis/entity_extend.yml`) | `loadClassMetadata` listener, vendor edit |
| Seed enum options (with translations) idempotently | EntityExtendBundle (`enum_values.yml`) | direct option inserts |
| Drop a deleted entity/field from entity config | EntityExtendBundle (`entity_cleanup.yml`) | manual SQL deletes |
| Query a jsonb column | EntityExtendBundle (`aaxis_jsonb_*` DQL functions) | native SQL |
| Override a method of an Oro service | AspectBundle (interceptor) | `decorates:` on a typehinted class, class swap |
| E2e data, runtime test state, index/visibility sync for fixtures | TestBundle (Alice fixture tags, `aaxis:test:action`, sync commands) | global reindex or cache clear, truncating purge on real entities |
| Configurable cron schedule | CronBundle (no README) | hard-coded schedule |
| Async outbound send with persisted state and retry | IntegrationBundle (README partly stale: trust code) | ad hoc MQ processors without state |
| External REST call with logging and retention | RestClientBundle | raw Guzzle without logging |
| Call an LLM or similar external provider | AiIntegrationBundle (provider interface, resolver, cache) | direct vendor SDK calls |
| Re-runnable seeding of editable CMS content or email templates | CMSBundle / EmailBundle (hash-guarded fixtures; no README) | overwrite on every version bump |
| Roles that may perform an action | SecurityBundle (permission role resolver; no README) | reading `oro_acl_entry` |
| Layout block rendered as an arbitrary HTML tag | LayoutBundle (no README) | custom block type |
| Datagrid filter pruned to existing values, jsonb path filter | FilterBundle | custom filter extension |
| Admin UI for URL redirects | RedirectBundle | custom admin pages |
| Queue depth on the admin dashboard | RabbitMQMonitorBundle (AMQP only; no README) | |
| Back-office menu colours from system config | UIBundle (admin only; no README) | |
| Throwaway experiment against the real app | AppBundle (git-excluded) | shipping or depending on it |

Known soft spots: FilterBundle's JSON path filter needs RestClientBundle present; IntegrationBundle and
RabbitMQMonitorBundle have rough edges; CMSBundle's unsecured WYSIWYG toggle defaults on (a security
decision to review per project).
