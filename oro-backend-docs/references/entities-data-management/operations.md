# OroCommerce Operations (Actions)

> Source: https://doc.oroinc.com/master/backend/entities-data-management/actions/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I add a custom button to an entity view/edit page?"
- "How do I add a button to a datagrid (list page)?"
- "What is an Operation in OroCommerce?"
- "How do I create an action that runs when a user clicks a button?"
- "How do I configure preconditions to show/hide a button?"
- "What is an Action Group and how do I use it?"
- "How do I disable a built-in Oro operation?"
- "How is an Operation different from a Workflow transition?"
- "Where is the actions.yml file and what goes in it?"
- "How do I configure the button label, icon, and order for an operation?"

---

## 1. What Are Operations and Why Use Them?

**Operations** (also called Actions in some contexts) are single-action UI buttons that can be attached to:
- Entity view pages
- Entity edit pages
- Entity index/datagrid pages
- Any named Symfony route

When a user clicks the button, a configured set of PHP actions execute (optionally after collecting data via a form).

**WHY they exist:** Many business processes need a single, discrete user action that doesn't fit into a multi-step workflow (e.g., "Mark as Paid", "Duplicate Record", "Send Reminder Email"). Operations provide a lightweight, configuration-driven way to add these buttons without writing controllers.

### Operations vs Workflows vs Processes

| Feature | Operations | Workflows | Processes |
|---------|------------|-----------|-----------|
| Purpose | Single-action button on entity | Multi-step entity state machine | Automated background task |
| Trigger | User clicks a button | User performs a transition | Entity event (Doctrine) or cron |
| State | Stateless | Tracks current step | Stateless |
| UI | Toolbar/grid button | Step wizard + transition buttons | None (background only) |
| Use when | One-off action without persistent state | Business process with multiple stages | Automatic reaction to data changes |

---

## 2. File Location and Loading

Configuration lives in:
```
YourBundle/Resources/config/oro/actions.yml
```

Operations are loaded automatically when the bundle is installed. To reload:
```bash
php bin/console cache:clear
```

---

## 3. Complete Configuration Schema

### 3.1 Root Structure

```yaml
operations:
  operation_unique_name:       # Snake_case identifier, unique across application
    # ... operation configuration
```

### 3.2 Top-Level Operation Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | translatable string | Yes | — | Button label displayed to user |
| `substitute_operation` | string | No | — | Name of built-in operation this replaces |
| `enabled` | boolean | No | `true` | Enable or disable this operation |
| `page_reload` | boolean | No | `false` | Force full page reload after execution |
| `order` | integer | No | `0` | Order of the button among multiple operations (lower = first) |
| `acl_resource` | string | No | — | ACL resource ID; operation hidden if user lacks permission |
| `entities` | array | No | `[]` | Entity FQCN list; button appears on these entity pages |
| `routes` | array | No | `[]` | Symfony route names; button appears on these routes |
| `groups` | array | No | `[]` | UI groups to show this operation in |
| `datagrids` | array | No | `[]` | Datagrid names; button appears in these grids |
| `for_all_entities` | boolean | No | `false` | Show on all entity pages (use carefully) |
| `for_all_datagrids` | boolean | No | `false` | Show in all datagrids (use carefully) |
| `exclude_entities` | array | No | `[]` | Exclude specific entities (when `for_all_entities: true`) |
| `exclude_datagrids` | array | No | `[]` | Exclude specific datagrids (when `for_all_datagrids: true`) |
| `button_options` | object | No | `{}` | Button appearance and placement (see 3.3) |
| `frontend_options` | object | No | `{}` | Modal/page display options (see 3.4) |
| `form_options` | object | No | `{}` | Form shown before execution (see 3.5) |
| `attributes` | object | No | `{}` | Attribute definitions for form data (see 3.6) |
| `preconditions` | conditions | No | — | Conditions that control button visibility |
| `conditions` | conditions | No | — | Conditions that must pass for execution |
| `preactions` | array | No | `[]` | Actions run before precondition evaluation |
| `form_init` | array | No | `[]` | Actions run before form display |
| `actions` | array | No | `[]` | Actions executed after user confirms |

---

### 3.3 Button Options

Controls where and how the button appears in the UI.

```yaml
button_options:
  icon: string              # Font Awesome CSS class (e.g., 'fa-envelope')
  class: string             # Additional CSS class (e.g., 'btn-danger')
  group: string             # Group dropdown label (buttons grouped under one dropdown)
  template: string          # Custom Twig template for button rendering
  page_component_module: string   # RequireJS module for frontend component
  page_component_options: object  # Options passed to frontend component
  data:
    page_component_module: string
    page_component_options: object
```

**Example:**
```yaml
button_options:
  icon: 'fa-paper-plane'
  class: 'btn-primary'
  group: 'More Actions'
```

---

### 3.4 Frontend Options

Controls how the operation dialog or page renders.

```yaml
frontend_options:
  template: string            # Custom Twig template for the form/confirmation dialog
  title: string               # Dialog or page title
  title_parameters: object    # Parameters for title translation
  options:
    width: integer            # Dialog width in pixels (e.g., 600)
    modal: boolean            # Whether dialog is modal (default: true)
    allowMaximize: boolean
    allowMinimize: boolean
```

---

### 3.5 Form Options

If an operation needs to collect data from the user before executing, configure a form here.

```yaml
form_options:
  attribute_fields:            # Which attributes to show as form fields
    attribute_name:
      form_type: string        # Symfony form type FQCN or alias
      options:                 # Options passed to the form type
        label: string
        required: boolean
        constraints:
          - NotBlank: ~
  attribute_default_values:    # Pre-populate attribute values
    attribute_name: value
```

**Example:**
```yaml
form_options:
  attribute_fields:
    reason:
      form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
      options:
        label: 'Cancellation Reason'
        required: true
        constraints:
          - NotBlank: ~
          - Length:
              max: 500
    notify_customer:
      form_type: Symfony\Component\Form\Extension\Core\Type\CheckboxType
      options:
        label: 'Notify Customer via Email'
        required: false
  attribute_default_values:
    notify_customer: true
```

---

### 3.6 Attributes

Define the data attributes used in forms and actions. Same type system as workflow attributes.

```yaml
attributes:
  attribute_name:
    type: string              # boolean, integer, float, string, array, object, entity
    label: translatable
    default: value
    options:
      class: string           # FQCN for entity/object types
      multiple: boolean       # Multiple values allowed (entity type)
```

**Example:**
```yaml
attributes:
  reason:
    type: string
    label: 'Reason'
  notify_customer:
    type: boolean
    label: 'Notify Customer'
    default: true
  replacement_order:
    type: entity
    label: 'Replacement Order'
    options:
      class: Acme\Bundle\OrderBundle\Entity\Order
```

---

### 3.7 Preconditions and Conditions

**Preconditions** control whether the button is visible. **Conditions** control whether the action can execute. Same condition syntax as workflows.

```yaml
preconditions:
  '@and':
    - '@acl_granted': 'acme_order_cancel'
    - '@equal': [$entity.status, 'pending']
    - '@not_blank': [$entity.id]

conditions:
  '@not_blank': [$reason]
```

**Common Conditions:**

| Condition | Syntax | Description |
|-----------|--------|-------------|
| `@and` | `'@and': [conditions]` | All must pass |
| `@or` | `'@or': [conditions]` | At least one must pass |
| `@not` | `'@not': condition` | Negates condition |
| `@equal` | `'@equal': [left, right]` | Equality check |
| `@not_equal` | `'@not_equal': [left, right]` | Inequality check |
| `@blank` | `'@blank': value` | Null or empty |
| `@not_blank` | `'@not_blank': value` | Not null or empty |
| `@greater` | `'@greater': [left, right]` | left > right |
| `@less` | `'@less': [left, right]` | left < right |
| `@instanceof` | `'@instanceof': [value, FQCN]` | Class instanceof check |
| `@acl_granted` | `'@acl_granted': resource` | User has ACL permission |
| `@type` | `'@type': [value, type]` | PHP type check |

---

### 3.8 Actions

Actions are executed after the user confirms the operation. Same action system as workflows.

```yaml
actions:
  - '@action_name': parameters
  - '@action_name':
      option1: value1
      option2: value2
```

**Common Actions:**

| Action | Parameters | Description |
|--------|------------|-------------|
| `@assign_value` | `[target, value]` | Set a value on a property path |
| `@assign_active_user` | `[target]` | Set target to logged-in user |
| `@create_object` | `{class, attribute, parameters}` | Instantiate a PHP object |
| `@create_entity` | `{class, attribute, data, flush}` | Create and optionally persist entity |
| `@find_entity` | `{class, attribute, where, order_by}` | Find entity by criteria |
| `@remove_entity` | `[entity]` | Delete an entity from database |
| `@flush_entity` | `[entity]` | Persist changes to database |
| `@format_string` | `{attribute, string, arguments}` | Format string with params |
| `@send_email` | `{from, to, subject, template, entity}` | Send email notification |
| `@flash_message` | `{message, type}` | Display flash message (success/error/warning) |
| `@redirect` | `{route, route_parameters}` | Redirect to a route |
| `@refresh_grid` | `[datagrid_name]` | Refresh a datagrid |
| `@call_service_method` | `{service, method, method_parameters, attribute}` | Call a DI service method |
| `@run_action_group` | `{action_group, parameters, results}` | Execute a named action group |
| `@copy_values` | `{to, from, ignore_empty}` | Copy property values between objects |
| `@unset_value` | `[path]` | Unset a value at property path |
| `@transit_workflow` | `{entity, workflow, transition}` | Trigger a workflow transition |
| `@close_workflow` | `[entity]` | Close the workflow for an entity |

**Action Syntax Variants:**

```yaml
# Short form (positional parameters)
actions:
  - '@assign_value': [$entity.status, 'cancelled']

# Long form (named parameters)
actions:
  - '@call_service_method':
      service: acme.order.service
      method: cancel
      method_parameters: [$entity, $reason]
      attribute: $result

# With conditions and break_on_failure
actions:
  - '@send_email':
      conditions:
        '@equal': [$notify_customer, true]
      parameters:
        from: 'noreply@example.com'
        to: [$entity.customer.email]
        subject: 'Order Cancelled'
        template: 'acme_order_cancelled'
      break_on_failure: false    # Log error but continue if email fails
```

---

## 4. Action Groups

Action Groups are reusable, named sequences of actions that can be called from operations, workflows, or other action groups.

### 4.1 Configuration

Action groups are configured in the same `actions.yml` file under the `action_groups` key:

```yaml
action_groups:
  acme_send_order_notification:
    parameters:
      order:
        type: Acme\Bundle\OrderBundle\Entity\Order
      message_type:
        type: string
        default: 'info'
    conditions:
      '@not_blank': $order.customer.email
    actions:
      - '@send_email':
          from: 'noreply@example.com'
          to: [$order.customer.email]
          subject: 'Order Update'
          template: 'acme_order_notification'
          entity: $order
      - '@flash_message':
          message: 'Notification sent'
          type: $message_type
```

### 4.2 Action Group Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `parameters` | object | No | Named input parameters with optional type and default |
| `conditions` | conditions | No | Conditions to check before executing |
| `actions` | array | Yes | The actions to execute |
| `acl_resource` | string | No | ACL check for this action group |

### 4.3 Calling an Action Group

From an operation:
```yaml
actions:
  - '@run_action_group':
      action_group: acme_send_order_notification
      parameters:
        order: $entity
        message_type: 'success'
      results:
        notification_sent: $.result
```

---

## 5. Disabling Built-in Operations

To disable an Oro-provided operation for specific entities:

```yaml
operations:
  oro_delete_entity:
    enabled: false              # Disable globally
    # OR target specific entities via workflows (disable_operations)
```

Within a workflow definition:
```yaml
workflows:
  my_order_workflow:
    disable_operations:
      Acme\Bundle\OrderBundle\Entity\Order:
        - oro_delete_entity     # Disable delete button when this workflow is active
```

---

## 6. Annotated Complete Example

```yaml
# src/Acme/Bundle/OrderBundle/Resources/config/oro/actions.yml

operations:

  acme_cancel_order:

    # ---- META ----
    label: 'Cancel Order'
    order: 10                                               # Position among operation buttons
    enabled: true
    acl_resource: acme_order_cancel                        # ACL permission required

    # ---- WHERE THE BUTTON APPEARS ----
    entities:
      - Acme\Bundle\OrderBundle\Entity\Order               # Show on Order entity pages
    datagrids:
      - acme-order-grid                                    # Show in order list datagrid

    # ---- BUTTON APPEARANCE ----
    button_options:
      icon: 'fa-ban'
      class: 'btn-danger'
      group: 'More Actions'                               # Show in dropdown group

    # ---- DIALOG SETTINGS ----
    frontend_options:
      title: 'Cancel Order'
      options:
        width: 500

    # ---- ATTRIBUTES (form data) ----
    attributes:
      reason:
        type: string
        label: 'Cancellation Reason'
      notify_customer:
        type: boolean
        label: 'Notify Customer'
        default: true

    # ---- FORM ----
    form_options:
      attribute_fields:
        reason:
          form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
          options:
            label: 'Reason for Cancellation'
            required: true
            constraints:
              - NotBlank: ~
        notify_customer:
          form_type: Symfony\Component\Form\Extension\Core\Type\CheckboxType
          options:
            label: 'Send cancellation email to customer'
            required: false

    # ---- DATA PREPARATION (before form shows) ----
    preactions:
      - '@assign_value': [$notify_customer, true]          # Default checkbox to checked

    # ---- BUTTON VISIBILITY CONDITIONS ----
    preconditions:
      '@and':
        - '@acl_granted': 'acme_order_cancel'
        - '@not_equal': [$entity.status, 'cancelled']       # Hide if already cancelled
        - '@not_equal': [$entity.status, 'shipped']         # Hide if already shipped

    # ---- EXECUTION CONDITIONS ----
    conditions:
      '@not_blank': [$reason]                              # Must have a reason

    # ---- ACTIONS ON EXECUTE ----
    actions:
      - '@assign_value': [$entity.status, 'cancelled']
      - '@assign_value': [$entity.cancellationReason, $reason]
      - '@assign_value': [$entity.cancelledAt, 'now']
      - '@flush_entity': [$entity]                         # Persist to database
      - '@run_action_group':                               # Reusable notification group
          action_group: acme_send_order_notification
          parameters:
            order: $entity
          conditions:
            '@equal': [$notify_customer, true]
      - '@flash_message':
          message: 'Order has been cancelled successfully'
          type: 'success'
      - '@refresh_grid': ['acme-order-grid']               # Update datagrid


  # ---- SIMPLE OPERATION (no form needed) ----
  acme_mark_order_paid:
    label: 'Mark as Paid'
    order: 20
    entities:
      - Acme\Bundle\OrderBundle\Entity\Order
    button_options:
      icon: 'fa-dollar'
      class: 'btn-success'
    preconditions:
      '@and':
        - '@acl_granted': 'acme_order_update'
        - '@equal': [$entity.paymentStatus, 'unpaid']
    actions:
      - '@assign_value': [$entity.paymentStatus, 'paid']
      - '@assign_value': [$entity.paidAt, 'now']
      - '@flush_entity': [$entity]
      - '@flash_message':
          message: 'Order marked as paid'
          type: 'success'


# ---- ACTION GROUPS ----
action_groups:

  acme_send_order_notification:
    parameters:
      order:
        type: Acme\Bundle\OrderBundle\Entity\Order
    conditions:
      '@not_blank': $order.customer.email
    actions:
      - '@send_email':
          from: 'noreply@example.com'
          to: [$order.customer.email]
          subject: 'Order Status Update'
          template: 'acme_order_status_notification'
          entity: $order
```

---

## 7. Property Path Syntax

Operations and workflows use a property path syntax to reference data:

| Path | Description |
|------|-------------|
| `$entity` | The entity the operation is acting on |
| `$entity.fieldName` | A field on the entity |
| `$entity.relation.field` | Nested relation field |
| `$attribute_name` | A defined attribute |
| `$.data.key` | Data context (available in forms) |
| `$context.userId` | Context values |

---

## 8. Adding Custom Actions and Conditions

### Custom Action

```php
// YourBundle/Action/MyCustomAction.php
namespace Acme\Bundle\OrderBundle\Action;

use Oro\Component\Action\Action\AbstractAction;
use Oro\Component\ConfigExpression\ContextAccessorAwareInterface;

class MyCustomAction extends AbstractAction
{
    protected function executeAction(mixed $context): void
    {
        $entity = $this->contextAccessor->getValue($context, $this->options['entity']);
        // ... perform action
    }

    public function initialize(array $options): static
    {
        // validate and store $options
        return $this;
    }
}
```

```yaml
# services.yml
services:
  Acme\Bundle\OrderBundle\Action\MyCustomAction:
    tags:
      - { name: oro_action.action, alias: acme_my_custom_action }
```

Usage in configuration:
```yaml
actions:
  - '@acme_my_custom_action':
      entity: $entity
      option1: value1
```

### Custom Condition

```php
// YourBundle/Condition/OrderIsPayable.php
namespace Acme\Bundle\OrderBundle\Condition;

use Oro\Component\ConfigExpression\Condition\AbstractCondition;

class OrderIsPayable extends AbstractCondition
{
    protected function isConditionAllowed(mixed $context): bool
    {
        $entity = $this->contextAccessor->getValue($context, $this->options[0]);
        return $entity->getTotalValue() > 0 && $entity->getPaymentStatus() === 'unpaid';
    }
}
```

```yaml
# services.yml
services:
  Acme\Bundle\OrderBundle\Condition\OrderIsPayable:
    tags:
      - { name: oro_action.condition, alias: acme_order_is_payable }
```

Usage:
```yaml
preconditions:
  '@acme_order_is_payable': [$entity]
```

---

## 9. Common Pitfalls

1. **`entities` vs `routes`**: Operations on entity pages should use `entities`. For custom controller routes, use `routes`. Both can be combined.
2. **Preconditions not filtering correctly**: The `$entity` variable is null when on a route without an entity context. Use `@not_blank: [$entity]` as the first precondition.
3. **Missing `@flush_entity`**: Changes to entity properties via `@assign_value` are not automatically persisted. Always call `@flush_entity` or use `@create_entity` with `flush: true`.
4. **Form attributes not matching `form_options`**: Every attribute referenced in `form_options.attribute_fields` must be declared in `attributes`.
5. **`acl_resource` is optional but recommended**: Without it, any logged-in user can trigger the operation if preconditions pass.
6. **Action Group parameters are typed**: If you declare `type: SomeClass` for a parameter, passing the wrong type will throw an error. Match types carefully.
7. **`page_reload: true` is disruptive**: Only use when the action fundamentally changes the page structure. Prefer `@refresh_grid` for grid-only updates.
