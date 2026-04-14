# OroCommerce Processes

> Source: https://doc.oroinc.com/master/backend/entities-data-management/processes/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I automatically react when an entity is created/updated/deleted?"
- "What is a Process in OroCommerce?"
- "How do I run code automatically on entity save?"
- "How do I schedule a background task to run on a cron schedule?"
- "What is the difference between a Process and a Workflow?"
- "How do I configure a process trigger?"
- "How do I prevent infinite loops in processes?"
- "How do I delay process execution (deferred/queued processes)?"
- "How do I load process configuration from YAML?"
- "How do I run a process trigger manually via CLI?"

---

## 1. What Are Processes and Why Use Them?

**Processes** are automated background tasks that execute in response to Doctrine entity lifecycle events (`create`, `update`, `delete`) or on a cron schedule. They are invisible to the end user — no buttons, no UI, just automatic execution.

**WHY they exist:** Many business requirements need automatic reactions to data changes — for example, "when an order status changes to 'shipped', automatically create a delivery record" or "every night, expire quotes older than 30 days." Processes handle these cases without requiring a user to click anything.

### Processes vs Workflows vs Operations

| Feature | Processes | Workflows | Operations |
|---------|-----------|-----------|------------|
| Purpose | Automated reaction to data change | Multi-step entity state machine | Single user-triggered action |
| Trigger | Doctrine entity events or cron | User action (transition) | User button click |
| User interaction | None | Step-by-step with forms | Single form/confirm dialog |
| Execution | Immediate or queued | Immediate | Immediate |
| State tracking | None | Tracks step on entity | None |
| Use when | Automatic side effect needed | Staged business process | On-demand user action |

**Key decision rule:**
- Use **Processes** when the trigger is a data event or time, not a user action.
- Use **Workflows** when a business process has multiple states a human navigates.
- Use **Operations** when a human needs to perform a one-off action with a button.

---

## 2. Core Architecture

### 2.1 Main Entities

**ProcessDefinition**
The main configuration entity. Contains:
- Target entity class (one definition per entity type)
- Actions to execute
- Execution order among multiple definitions for same entity
- Enabled/disabled status
- Preconditions to filter when to run

**ProcessTrigger**
Specifies when the definition executes. Two types:
- **Event trigger**: React to `create`, `update`, or `delete` Doctrine events
- **Cron trigger**: Run on a schedule

**ProcessJob**
Stores data for deferred (queued) process execution:
- Entity identity and class
- Change set (fields changed during `update` events)
- Link to the trigger that created the job
- Entity hash for deduplication

### 2.2 Execution Flow

**Immediate execution:**
1. Entity lifecycle event fires (e.g., `postFlush`)
2. System checks all process definitions for this entity class
3. Applicable triggers are identified
4. Preconditions are evaluated
5. If passed, actions execute immediately in the same request

**Deferred execution (queued: true):**
1. Entity lifecycle event fires
2. A `ProcessJob` is created and sent to the message queue
3. The message queue consumer processes the job asynchronously
4. Actions execute in the background

---

## 3. File Location and Loading

Configuration lives in:
```
YourBundle/Resources/config/oro/processes.yml
```

Load process definitions from YAML into the database:
```bash
php bin/console oro:process:configuration:load

# Options:
#   --directories=path    Scan specific directory paths
#   --definitions=name    Load only specific definition names
```

---

## 4. Complete Configuration Schema

### 4.1 Root Structure

```yaml
processes:
  definitions:
    definition_name:        # Unique snake_case identifier
      # ... definition properties
  triggers:
    definition_name:        # Must match a definition name
      - # ... trigger configuration
      - # ... additional triggers for same definition
```

### 4.2 Process Definition Properties

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | string | Yes | — | Human-readable name shown in admin UI |
| `enabled` | boolean | No | `true` | Enable or disable this process definition |
| `entity` | string (FQCN) | Yes | — | Fully qualified class name of the entity this process watches |
| `order` | integer | No | `0` | Execution order when multiple definitions target same entity (lower = first) |
| `exclude_definitions` | array | No | `[]` | Names of other process definitions to skip while this one executes (prevents recursion) |
| `preconditions` | conditions | No | — | Conditions evaluated against the entity before executing actions |
| `actions_configuration` | array | Yes | — | List of actions to execute (same syntax as workflow actions) |

```yaml
processes:
  definitions:
    acme_on_order_ship:
      label: 'Create Delivery Record on Order Ship'
      enabled: true
      entity: Acme\Bundle\OrderBundle\Entity\Order
      order: 10
      exclude_definitions: [acme_on_delivery_create]    # Prevent loop
      preconditions:
        '@equal': [$entity.status, 'shipped']           # Only run for shipped orders
      actions_configuration:
        - '@create_entity':
            class: Acme\Bundle\OrderBundle\Entity\Delivery
            flush: true
            data:
              order: $entity
              createdAt: 'now'
              status: 'pending'
```

### 4.3 Process Trigger Properties

#### Event Trigger

Fires on Doctrine entity lifecycle events:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `event` | string | Yes | — | `create`, `update`, or `delete` |
| `field` | string | No | — | Entity field name; only fire when this field changes (update events only) |
| `priority` | integer | No | `0` | Job queue priority (higher = processed first) |
| `queued` | boolean | No | `true` | If `true`, execute via message queue (async). If `false`, execute immediately |
| `time_shift` | integer | No | `0` | Delay execution by N seconds (requires `queued: true`) |

```yaml
triggers:
  acme_on_order_ship:
    - event: update
      field: status                  # Only trigger when 'status' field changes
      queued: true                   # Async via message queue
      priority: 10
    - event: create
      queued: false                  # Immediate execution on create
```

#### Cron Trigger

Fires on a cron schedule:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `cron` | string | Yes | — | Standard cron expression (e.g., `0 9 * * 1`) |
| `queued` | boolean | No | `true` | Process via message queue |
| `filter` | string | No | — | DQL/expression to filter which entity records to process |

```yaml
triggers:
  acme_expire_old_quotes:
    - cron: '0 2 * * *'             # Run at 2am daily
      queued: true
      filter: 'e.status = ''active'' AND e.expiresAt < NOW()'
```

**Note:** For cron triggers, the process runs against all records matching the filter. The system iterates over matching entity records and executes the process definition actions for each.

---

## 5. Actions in Processes

Processes use the same action system as workflows and operations. Actions are listed under `actions_configuration`.

**Commonly used process actions:**

| Action | Description |
|--------|-------------|
| `@assign_value` | Set a property value: `[$entity.field, value]` |
| `@create_entity` | Create and persist a new entity |
| `@find_entity` | Find an entity by criteria |
| `@remove_entity` | Delete an entity |
| `@flush_entity` | Persist changes to database |
| `@call_service_method` | Call a service method |
| `@send_email` | Send an email notification |
| `@format_string` | Format a string |
| `@run_action_group` | Execute a named action group |

**Referencing the entity in actions:**

In process actions, the entity being processed is accessible as `$entity`. Change set data (for update events) is available via the process job context.

```yaml
actions_configuration:
  - '@assign_value': [$entity.lastModifiedAt, 'now']
  - '@call_service_method':
      service: acme.notification.service
      method: notifyStatusChange
      method_parameters: [$entity]
  - '@flush_entity': [$entity]
```

---

## 6. Preventing Infinite Loops

Processes can trigger other processes. For example, process A updates entity X, which triggers process B, which updates entity Y, which triggers process A again — infinite recursion.

**Prevention strategies:**

### Strategy 1: `exclude_definitions`

Explicitly skip other process definitions while this one runs:

```yaml
definitions:
  acme_on_order_update:
    exclude_definitions: [acme_on_order_invoice_update]
    actions_configuration:
      - '@assign_value': [$entity.lastSyncedAt, 'now']
      - '@flush_entity': [$entity]
```

### Strategy 2: Targeted preconditions

Only run when a specific condition is met (not every time the entity changes):

```yaml
definitions:
  acme_set_shipped_at:
    preconditions:
      '@and':
        - '@equal': [$entity.status, 'shipped']
        - '@blank': [$entity.shippedAt]            # Only run once (not on subsequent saves)
    actions_configuration:
      - '@assign_value': [$entity.shippedAt, 'now']
      - '@flush_entity': [$entity]
```

### Strategy 3: Field-specific triggers

Only trigger on a specific field change to avoid broad update loops:

```yaml
triggers:
  acme_set_shipped_at:
    - event: update
      field: status                 # Only fires when 'status' specifically changes
```

---

## 7. Annotated Complete Example

```yaml
# src/Acme/Bundle/OrderBundle/Resources/config/oro/processes.yml

processes:

  definitions:

    # ---- EXAMPLE 1: React to entity update (specific field) ----
    acme_on_order_shipped:
      label: 'On Order Shipped: Create Delivery and Notify'
      enabled: true
      entity: Acme\Bundle\OrderBundle\Entity\Order
      order: 10
      exclude_definitions:
        - acme_on_delivery_created   # Prevent loop when we create delivery
      preconditions:
        '@and':
          - '@equal': [$entity.status, 'shipped']
          - '@blank': [$entity.shippedAt]          # Only process once
      actions_configuration:
        # Record the ship timestamp
        - '@assign_value': [$entity.shippedAt, 'now']

        # Create a delivery record
        - '@create_entity':
            class: Acme\Bundle\OrderBundle\Entity\Delivery
            attribute: $delivery
            flush: true
            data:
              order: $entity
              status: 'in_transit'
              createdAt: 'now'
              trackingNumber: ''

        # Notify the customer
        - '@send_email':
            from: 'noreply@example.com'
            to: [$entity.customer.email]
            subject: 'Your Order Has Shipped'
            template: 'acme_order_shipped_notification'
            entity: $entity

        # Flush entity changes
        - '@flush_entity': [$entity]


    # ---- EXAMPLE 2: React to entity creation ----
    acme_on_order_created:
      label: 'On Order Created: Initialize Workflow Data'
      enabled: true
      entity: Acme\Bundle\OrderBundle\Entity\Order
      order: 5
      actions_configuration:
        - '@assign_value': [$entity.internalCode, null]
        - '@call_service_method':
            service: acme.order.code_generator
            method: generateCode
            method_parameters: [$entity]
            attribute: $generatedCode
        - '@assign_value': [$entity.internalCode, $generatedCode]
        - '@flush_entity': [$entity]


    # ---- EXAMPLE 3: Cron-based batch processing ----
    acme_expire_unpaid_orders:
      label: 'Expire Unpaid Orders Older Than 24 Hours'
      enabled: true
      entity: Acme\Bundle\OrderBundle\Entity\Order
      order: 20
      preconditions:
        '@and':
          - '@equal': [$entity.status, 'pending_payment']
          - '@not_blank': [$entity.createdAt]
      actions_configuration:
        - '@assign_value': [$entity.status, 'expired']
        - '@assign_value': [$entity.expiredAt, 'now']
        - '@send_email':
            from: 'noreply@example.com'
            to: [$entity.customer.email]
            subject: 'Your Order Has Expired'
            template: 'acme_order_expired_notification'
            entity: $entity
        - '@flush_entity': [$entity]


  triggers:

    # ---- Triggers for acme_on_order_shipped ----
    acme_on_order_shipped:
      - event: update
        field: status                # Only when status field changes
        queued: true                 # Async — don't block the web request
        priority: 10

    # ---- Triggers for acme_on_order_created ----
    acme_on_order_created:
      - event: create
        queued: false                # Immediate — needs to run in same request

    # ---- Triggers for acme_expire_unpaid_orders (cron) ----
    acme_expire_unpaid_orders:
      - cron: '0 * * * *'           # Run every hour
        queued: true
        filter: >
          e.status = 'pending_payment'
          AND e.createdAt < DATE_SUB(NOW(), 1, 'day')
```

---

## 8. Console Commands Reference

```bash
# Load process definitions from YAML into the database
php bin/console oro:process:configuration:load

# Load specific definitions only
php bin/console oro:process:configuration:load --definitions=acme_on_order_shipped

# Load from specific directory
php bin/console oro:process:configuration:load --directories=src/Acme/Bundle/OrderBundle

# Execute a specific trigger manually (useful for testing)
php bin/console oro:process:handle-trigger --id=42 --name=acme_on_order_shipped
# --id    = ProcessTrigger entity ID
# --name  = ProcessDefinition name

# Activate a process via REST API route:
# GET /api/processes/activate/{processDefinition}
# GET /api/processes/deactivate/{processDefinition}
```

---

## 9. REST API Management

Processes can be activated and deactivated via REST API:

| Action | Route | Parameter |
|--------|-------|-----------|
| Activate | `oro_api_process_activate` | `processDefinition` (definition name) |
| Deactivate | `oro_api_process_deactivate` | `processDefinition` (definition name) |

---

## 10. Key Distinctions: When NOT to Use Processes

| Scenario | Use Instead | Reason |
|----------|-------------|--------|
| User needs to confirm or input data | Operation | Processes have no UI interaction |
| Entity has multiple discrete states | Workflow | Processes don't track state |
| Action should only happen when user explicitly requests it | Operation | Processes fire automatically |
| Complex multi-entity orchestration triggered by user | Workflow + Message Queue | Better control over execution context |
| High-frequency entity updates (e.g., inventory) | Custom event listener | Processes add database overhead per entity change |

---

## 11. Common Pitfalls

1. **Missing `exclude_definitions`**: If process A flushes entity changes that trigger process B which flushes entity changes that trigger process A, you get an infinite loop. Always audit for cycles.

2. **`queued: false` blocking web requests**: Immediate execution happens inside the user's HTTP request. Long-running actions will time out. Use `queued: true` for anything non-trivial.

3. **`field` filter only works for `update` events**: The `field` parameter is ignored on `create` and `delete` triggers.

4. **Preconditions not catching stale data**: When a process is deferred (queued), the entity state at execution time may differ from when the trigger fired. Preconditions are re-evaluated at execution time, so this is actually correct behavior — but make sure your preconditions are checking the right current state.

5. **`time_shift` requires `queued: true`**: You cannot delay immediate execution; deferred execution requires the message queue.

6. **Cron filters use DQL syntax**: The `filter` expression for cron triggers uses Doctrine DQL, not PHP. The alias `e` refers to the entity. Test your DQL filter carefully.

7. **Loading config doesn't overwrite database records automatically**: If you change a definition and reload, the database is updated. But if you delete a definition from YAML, it remains in the database until manually removed.

8. **Process jobs survive entity deletion only if `queued: true` and job was already created**: Deleting an entity removes its pending process jobs. If the entity is deleted before the job runs, the job is cancelled.
