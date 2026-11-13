# Debugging: async audit and message queue


Oro **Data Audit is asynchronous** — a mutation enqueues an audit message that a consumer must
process before the audit row exists and the **Change History** grid shows it. The broker is
**env-specific**: the `test` env typically uses the **DBAL** transport (`message_queue_transport_dsn: 'dbal:'`
→ the `oro_message_queue` table), while the `prod` env (the one FPM serves the browser from) usually
uses **RabbitMQ** (`ORO_MQ_DSN=amqp://…`). So a **browser-driven** save enqueues on RabbitMQ, not
the DBAL table — drain the broker the mutation actually used before asserting.

⚠️ **Poison audit messages on a shared dev broker.** In dev **no consumer runs**, so the prod
RabbitMQ queue (`oro.default`) accumulates a backlog. Worse, it fills with **poison messages**: an
audit for a `LocalizedFallbackValue` whose `Localization` an earlier feature created then **deleted**.
Processing it walks `ChangeSetToAuditFieldsConverter → EntityNameProvider →
LocalizedFallbackValueNameProvider->getName() → Localization->getName()` on a missing entity →
`EntityNotFoundException` → **the consumer crashes**. A harness consume step that swallows the error
silently dies before reaching the scenario's own fresh audit message → the audit row never appears →
the Change History grid stays empty.

**Symptom signature:** the step times out on `locator.waitFor` for `.ui-dialog .grid-container` to
be **visible** (the grid mounts but stays *hidden* because it has **zero rows**) — NOT the step's own
"grid does not contain X" assertion. An empty/hidden audit grid means *no audit was recorded*, which
is an **async/broker** problem, not a selector, ACL, or `dataaudit.auditable` config problem. Confirm
the field/entity are auditable in the live `oro_entity_config[_field]` before suspecting config; if
they are, look at the queue.

**In-harness durable fix (implemented):** each feature's `AfterAll` runs `drainProdQueue` — a
**single** `oro:message-queue:consume --time-limit="+12 seconds"` pass against the prod env, serving
as both settle window and drain. Oro flushes buffered audit messages on `kernel.terminate` (after
the HTTP response returns), so a benign audit can arrive on the broker tens of seconds after the
scenario step finishes; the consumer holds a **live subscription for the whole window** (its receive
loop keeps polling until the time limit), so a message landing mid-window is still received and
processed in the same pass — no separate wait needed. **Poison is detected by matching
`EntityNotFoundException` in the captured stdout+stderr** (not by exit code — the consumer also
exits non-zero on its normal time/message limit; a clean expiry prints only `"The limit time has
passed."`, never that exception). Only when poison is detected does the `AfterAll` call
`purgeProdQueue()` (`rabbitmqctl purge_queue oro.default`) and throw — the feature **fails**. Raw
queue depth is never a fail signal. There is **no purge-before guard** — a raw-depth purge before
consuming would race concurrent workers on the shared broker. `prodQueueDepth()` is a
manual-diagnostic helper only — the teardown no longer calls it. To clear a pre-existing backlog by
hand before a run: `docker exec <rabbitmq-container> rabbitmqctl purge_queue oro.default` (verify with
`rabbitmqctl list_queues name messages_ready` → 0).

