# OroCommerce Workflows

> Source: https://doc.oroinc.com/master/backend/entities-data-management/workflows/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I create a workflow in OroCommerce?"
- "What is a workflow step / transition / transition_definition?"
- "How do I add conditions to a workflow transition?"
- "How do I trigger a workflow on entity events or cron?"
- "How do I restrict field editing based on workflow step?"
- "How do I configure a form that appears during a workflow transition?"
- "What workflow events can I listen to?"
- "How do I make a workflow exclusive (only one active at a time)?"
- "What is the difference between preconditions and conditions in workflows?"
- "How do I import/extend an existing workflow?"

---

## 1. What Are Workflows and Why Use Them?

A **workflow** in OroCommerce is a state machine that governs how an entity record transitions through a defined series of states (steps). It enforces business rules by:

- Restricting which transitions are available based on the current step
- Requiring conditions to be met before a transition can execute
- Executing actions automatically when a transition occurs
- Optionally presenting a form to the user to collect additional data
- Restricting field editing at certain steps

**WHY they exist:** Workflows encode business processes that involve multiple discrete states and human decision points (e.g., "Sales Opportunity: Qualify → Present → Close"). They prevent users from performing contradictory actions (e.g., closing an unqualified opportunity) and ensure all required data is collected at each stage.

### Workflows vs Operations vs Processes

| Feature | Workflows | Operations | Processes |
|---------|-----------|------------|-----------|
| Purpose | Multi-step entity state machine | Single-action button on entity | Automated background task |
| Trigger | Manual user action (transitions) | Manual user action (button click) | Entity lifecycle events (create/update/delete) or cron |
| UI | Steps displayed, buttons per step | Button in entity toolbar/grid | No UI — background only |
| State | Tracks current step on entity | Stateless | Stateless |
| Use when | Multi-state business process | One-off action on entity | Automatic reaction to data changes |

---

## 2. File Location and Loading

Configuration lives in:
```
YourBundle/Resources/config/oro/workflows.yml
```

Load definitions into the database after changes:
```bash
php bin/console oro:workflow:definitions:load
# Options:
#   --directories=path  Scan specific directories
#   --workflows=name    Load only specific workflow names
```

---

## 3. Complete Configuration Schema

### 3.1 Root Structure

```yaml
workflows:
  workflow_unique_name:       # Snake_case identifier, unique across the application
    # ... workflow properties
```

### 3.2 Workflow-Level Properties

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | translatable string | Yes | — | UI display name. Translation key: `oro.workflow.{name}.label` |
| `entity` | string (FQCN) | Yes | — | Fully qualified class name of the entity this workflow manages |
| `entity_attribute` | string | No | `entity` | Name of the workflow attribute that holds the related entity |
| `is_system` | boolean | No | `false` | If `true`, cannot be edited or removed through the admin UI |
| `start_step` | string | No* | — | Name of the initial step. *Required if no `is_start: true` transition exists |
| `steps_display_ordered` | boolean | No | `false` | Show all steps in UI wizard order (useful for sales funnels) |
| `priority` | integer | No | `0` | Determines dominance when multiple workflows compete. Higher = more dominant |
| `exclusive_active_groups` | array | No | `[]` | Group names; only one workflow per group can be active at a time |
| `exclusive_record_groups` | array | No | `[]` | Group names; prevents concurrent transitions on the same entity record |
| `active` | boolean | No | `false` | Activate immediately on first configuration load |
| `applications` | array | No | `[]` | Web application names where this workflow is available (e.g., `[commerce]`) |
| `scopes` | array | No | `[]` | Scope configurations for filtering workflow availability |
| `datagrids` | array | No | `[]` | Datagrid names where transition buttons appear |
| `disable_operations` | object | No | `{}` | Operations to disable when this workflow is active, keyed by entity class |
| `defaults` | object | No | `{}` | Default configuration values (commonly `active: true`) |
| `metadata` | array | No | `[]` | Arbitrary metadata attached to the workflow |

```yaml
workflows:
  my_order_workflow:
    label: 'My Order Workflow'
    entity: Acme\Bundle\OrderBundle\Entity\Order
    entity_attribute: order
    is_system: true
    start_step: pending
    steps_display_ordered: true
    priority: 100
    exclusive_active_groups: [order_flow]
    exclusive_record_groups: [order_processing]
    active: true
    applications: [commerce]
    datagrids: [orders-grid]
    disable_operations:
      Acme\Bundle\OrderBundle\Entity\Order: [acme_cancel_order]
    defaults:
      active: true
```

---

### 3.3 Steps Configuration

Steps represent the states an entity can be in. Each step defines which transitions are allowed from that state.

```yaml
steps:
  step_name:
    label: translatable        # Translation key: oro.workflow.{workflow}.step.{name}.label
    order: integer             # Position in wizard display (used with steps_display_ordered)
    is_final: boolean          # Marks this as a terminal state (no transitions out)
    allowed_transitions:       # List of transition names available from this step
      - transition_name_1
      - transition_name_2
    entity_acl:                # ACL restrictions while entity is in this step
      update: boolean          # Can the entity be edited?
      delete: boolean          # Can the entity be deleted?
```

**Example:**
```yaml
steps:
  pending:
    label: 'Pending'
    order: 10
    allowed_transitions: [approve, reject]
    entity_acl:
      delete: false            # Cannot delete while pending

  approved:
    label: 'Approved'
    order: 20
    allowed_transitions: [ship]
    entity_acl:
      update: false            # Cannot edit approved orders

  shipped:
    label: 'Shipped'
    order: 30
    is_final: true             # No further transitions possible
```

---

### 3.4 Attributes Configuration

Attributes are workflow-scoped variables that persist with the workflow item (separate from the entity itself).

```yaml
attributes:
  attribute_name:
    type: string               # Required — see supported types below
    label: translatable        # Translation key: oro.workflow.{workflow}.attribute.{name}.label
    default: value             # Optional default value
    property_path: string      # Map to entity property (e.g., entity.status)
    entity_acl:                # ACL on attribute when used as entity reference
      update: boolean
      delete: boolean
    options:
      class: string            # FQCN — required for type: entity or type: object
      multiple: boolean        # Allow multiple values (type: entity only)
      virtual: boolean         # Not persisted to database
```

**Supported Attribute Types:**

| Type | Aliases | Description |
|------|---------|-------------|
| `boolean` | `bool` | True/false value |
| `integer` | `int` | Integer number |
| `float` | — | Decimal number |
| `string` | — | Text value |
| `array` | — | Array of values |
| `object` | — | PHP object (must specify `options.class`) |
| `entity` | — | Doctrine entity reference (must specify `options.class`) |

**Example:**
```yaml
attributes:
  order:
    type: entity
    options:
      class: Acme\Bundle\OrderBundle\Entity\Order
  notes:
    type: string
    label: 'Approval Notes'
  approved_by:
    type: entity
    options:
      class: Oro\Bundle\UserBundle\Entity\User
  rejection_reason:
    type: string
    property_path: entity.rejectionReason   # Synced to entity field
```

---

### 3.5 Transitions Configuration

Transitions define the rules for moving from one step to another.

```yaml
transitions:
  transition_name:
    label: translatable              # Translation key: oro.workflow.{workflow}.transition.{name}.label
    button_label: translatable       # Text shown on the button
    button_title: translatable       # Tooltip/hover text
    step_to: string                  # Target step name after successful transition
    conditional_steps_to:            # Conditionally route to different steps
      step_name: '@condition_expression'
    transition_definition: string    # Name of the transition_definition to use
    transition_service: string       # DI service ID implementing TransitionServiceInterface
    is_start: boolean                # Can this transition start the workflow? (default: false)
    is_hidden: boolean               # Hide from UI (default: false)
    is_unavailable_hidden: boolean   # Hide button when transition unavailable (default: false)
    acl_resource: string             # ACL resource to check before showing button
    acl_message: string              # Message shown when ACL check fails
    message: translatable            # Warning shown before execution (key: oro.workflow.{workflow}.transition.{name}.warning_message)
    message_parameters: array        # Parameters for the warning message translation
    init_routes: [route_names]       # Routes where this transition can initiate the workflow
    init_entities: [entity_classes]  # Entity pages where this transition can start the workflow
    init_datagrids: [datagrid_names] # Datagrids where this transition appears as a start button
    init_context_attribute: string   # Attribute storing init context (default: init_context)
    display_type: string             # How transition form displays: 'dialog' or 'page'
    destination_page: string         # After transition: 'name', 'index', 'view', or ~ (stay)
    page_template: string            # Custom Twig template path for page display
    dialog_template: string          # Custom Twig template path for dialog display
    frontend_options:
      class: string                  # CSS class for the button
      icon: string                   # Icon CSS class (e.g., 'fa-check')
    form_options:                    # Form shown to user during transition
      attribute_fields: {}           # See Section 4: Transition Forms
      form_init: []                  # Actions to run before form display
    triggers: []                     # Automatic trigger configuration (see Section 5)
```

**Example:**
```yaml
transitions:
  approve:
    label: 'Approve Order'
    button_label: 'Approve'
    button_title: 'Approve this order for fulfillment'
    step_to: approved
    transition_definition: approve_definition
    acl_resource: acme_order_approve
    message: 'Are you sure you want to approve this order?'
    display_type: dialog
    destination_page: view
    frontend_options:
      icon: 'fa-check'
      class: 'btn-success'
    form_options:
      attribute_fields:
        notes:
          form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
          options:
            required: false
            label: 'Approval Notes'

  reject:
    label: 'Reject Order'
    step_to: rejected
    transition_definition: reject_definition
    display_type: dialog
    form_options:
      attribute_fields:
        rejection_reason:
          form_type: Symfony\Component\Form\Extension\Core\Type\TextType
          options:
            required: true
            constraints:
              - NotBlank: ~
```

---

### 3.6 Transition Definitions Configuration

Transition definitions contain the actual business logic: what conditions must be met and what actions to execute.

```yaml
transition_definitions:
  definition_name:
    preactions:           # Actions run BEFORE precondition evaluation (data preparation)
      - '@action_name': parameters
    preconditions:        # Conditions that control whether the transition BUTTON is visible
      '@condition_name': parameters
    conditions:           # Conditions that must pass for the transition to EXECUTE
      '@condition_name': parameters
    actions:              # Actions executed AFTER the transition succeeds
      - '@action_name': parameters
```

**Execution order:**
1. `preactions` — prepare data (always runs when button is checked)
2. `preconditions` — if fails, button is hidden/disabled
3. (user clicks button)
4. `conditions` — if fails, transition is blocked with error message
5. Transition moves entity to `step_to`
6. `actions` — perform side effects (send email, update fields, etc.)

**WHY the split between preconditions and conditions:**
- `preconditions` control UI visibility (should the button show?)
- `conditions` enforce business rules when the user actually tries to execute

**Common Conditions:**

| Condition | Parameters | Description |
|-----------|------------|-------------|
| `@and` | array of conditions | All conditions must pass |
| `@or` | array of conditions | At least one must pass |
| `@not` | condition | Negates the condition |
| `@equal` | [left, right] | Values are equal |
| `@not_equal` | [left, right] | Values are not equal |
| `@blank` | value | Value is null or empty |
| `@not_blank` | value | Value is not null or empty |
| `@greater` | [left, right] | left > right |
| `@greater_or_equal` | [left, right] | left >= right |
| `@less` | [left, right] | left < right |
| `@less_or_equal` | [left, right] | left <= right |
| `@instanceof` | [value, class] | Value is instance of class |
| `@acl_granted` | resource | Current user has ACL permission |

**Common Actions:**

| Action | Description |
|--------|-------------|
| `@assign_value` | Set attribute value: `[$attribute, value]` |
| `@assign_active_user` | Set attribute to currently logged-in user |
| `@create_object` | Instantiate a PHP object |
| `@create_entity` | Create and persist a Doctrine entity |
| `@find_entity` | Find entity by criteria |
| `@format_string` | Format a string with parameters |
| `@send_email` | Send an email notification |
| `@flash_message` | Display a flash message to the user |
| `@close_workflow` | End the workflow for this entity |
| `@transit_workflow` | Trigger another workflow transition |
| `@call_service_method` | Call an arbitrary DI service method |
| `@run_action_group` | Execute a named action group |

**Example:**
```yaml
transition_definitions:
  approve_definition:
    preactions:
      - '@assign_active_user': [$approved_by]
    preconditions:
      '@and':
        - '@acl_granted': 'acme_order_approve'
        - '@equal': [$entity.status, 'pending']
    conditions:
      '@not_blank': [$entity.totalValue]
    actions:
      - '@assign_value': [$entity.status, 'approved']
      - '@assign_value': [$entity.approvedAt, 'now']
      - '@send_email':
          from: 'noreply@example.com'
          to: [$entity.customer.email]
          subject: 'Order Approved'
          template: 'acme_order_approved'

  reject_definition:
    conditions:
      '@not_blank': [$rejection_reason]
    actions:
      - '@assign_value': [$entity.status, 'rejected']
      - '@assign_value': [$entity.rejectionReason, $rejection_reason]
```

---

### 3.7 Variable Definitions

Variables are like workflow-level configuration values that can be set via the admin UI and reused across transitions.

```yaml
variable_definitions:
  variables:
    variable_name:
      type: string              # Same types as attributes
      value: initial_value      # Required: the initial/default value
      label: translatable       # Translation key: oro.workflow.{workflow}.variable.{name}.label
      property_path: string     # Optional mapping to entity property
      entity_acl:
        update: boolean
        delete: boolean
      options:
        class: string           # FQCN for entity/object types
        form_options:
          tooltip: boolean
          constraints:
            NotBlank: ~
        multiple: boolean       # For entity type
        identifier: string      # Entity identifier field name
```

**Example:**
```yaml
variable_definitions:
  variables:
    auto_approve_threshold:
      type: float
      value: 1000.00
      label: 'Auto-Approve Threshold Amount'
```

---

### 3.8 Entity Restrictions

Restrict editing of specific entity fields while the workflow is active or in a specific step.

```yaml
entity_restrictions:
  restriction_name:
    attribute: string    # Workflow attribute name referencing the entity
    field: string        # Entity field name to restrict
    mode: string         # 'full' (block all editing), 'disallow' (block specific values), 'allow' (allow only specific values)
    values: [array]      # Values for disallow/allow modes
    step: string         # Optional: only apply restriction in this step
```

**Example:**
```yaml
entity_restrictions:
  lock_status_after_approval:
    attribute: order
    field: status
    mode: full            # Field completely read-only
    step: approved        # Only in the approved step

  restrict_discount_values:
    attribute: order
    field: discountPercent
    mode: disallow
    values: [0]           # Cannot set discount to 0% once started
```

---

## 4. Transition Forms

When a transition requires user input, configure a form that appears before executing the transition.

### 4.1 Simple Attribute Form

The most common pattern — presents workflow attributes as form fields:

```yaml
transitions:
  submit_for_review:
    step_to: in_review
    transition_definition: submit_definition
    display_type: dialog         # Shows as modal dialog
    form_options:
      attribute_fields:
        reviewer_notes:
          form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
          options:
            label: 'Notes for Reviewer'
            required: true
            constraints:
              - NotBlank: ~
              - Length:
                  max: 1000
        priority:
          form_type: Symfony\Component\Form\Extension\Core\Type\ChoiceType
          options:
            choices:
              High: high
              Medium: medium
              Low: low
```

### 4.2 Form Init — Preparing Data Before Display

Use `form_init` to run actions before the form renders (e.g., populate a date picker with tomorrow's date):

```yaml
form_options:
  form_init:
    - '@create_object':
        class: \DateTime
        attribute: $.data.scheduled_date
        parameters: ['tomorrow']
    - '@find_entity':
        class: Acme\Bundle\UserBundle\Entity\User
        attribute: $.data.default_reviewer
        where:
          role: 'ROLE_REVIEWER'
  attribute_fields:
    scheduled_date:
      form_type: acme_date_picker
    default_reviewer:
      form_type: Oro\Bundle\UserBundle\Form\Type\UserSelectType
```

### 4.3 Custom Form Type

For complex forms (e.g., reusing an existing entity form):

```yaml
transitions:
  edit_quote:
    form_type: 'Oro\Bundle\SaleBundle\Form\Type\QuoteType'
    form_options:
      configuration:
        handler: 'default'                              # Use built-in handler or custom service ID
        template: '@OroSale/Quote/update.html.twig'    # Custom rendering template
        data_provider: 'quote_update'                   # Service providing template context
        data_attribute: 'quote'                         # Workflow attribute storing form data
      form_init:
        - '@assign_value': [$.data.quote, $entity]
      attribute_fields: ~                               # Omit when using custom form_type
```

### 4.4 Layout Context Variables

Available in layout-based transition form templates:

| Variable | Description |
|----------|-------------|
| `workflowName` | Current workflow identifier |
| `transitionName` | Current transition identifier |
| `transitionFormView` | Symfony form view object |
| `transition` | Transition model object |
| `workflowItem` | WorkflowItem entity |
| `formRouteName` | Route name for form submission |

---

## 5. Transition Triggers

Triggers allow transitions to fire automatically without user interaction.

### 5.1 Entity Event Trigger

Fires when a Doctrine entity event occurs:

```yaml
triggers:
  - entity_class: Acme\Bundle\OrderBundle\Entity\OrderLineItem
    event: update              # create | update | delete
    field: quantity            # Optional: only fire when this field changes (update only)
    queued: true               # Process via message queue (default: true)
    require: 'entity.quantity > 0'   # Expression Language condition
    relation: entity.order     # Property path from triggered entity to workflow entity
```

### 5.2 Cron Trigger

Fires on a cron schedule:

```yaml
triggers:
  - cron: '0 9 * * 1'         # Every Monday at 9am
    queued: true
    filter: 'wi.currentStep.name = "pending" AND e.createdAt < DATE_SUB(NOW(), 7, "day")'
```

**Filter aliases:**
- `e` — the managed entity
- `wd` — workflow definition
- `wi` — workflow item
- `ws` — workflow step

---

## 6. Workflow Events

The platform dispatches events during workflow execution. Subscribe to them to inject custom logic without modifying workflow YAML.

### 6.1 Event Dispatch Order

Events fire in this sequence during a transition:

1. **`oro_workflow.pre_announce`** — Before precondition checks (validate button visibility)
2. **`oro_workflow.announce`** — After precondition checks (validate button visibility)
3. **`oro_workflow.pre_guard`** — Before condition checks (validate transition execution)
4. **`oro_workflow.guard`** — After condition checks (validate transition execution)
5. **`oro_workflow.leave`** — Entity leaving current step
6. **`oro_workflow.start`** — Workflow starts at start step
7. **`oro_workflow.enter`** — Right before entering the new step
8. **`oro_workflow.entered`** — Right after entering the new step
9. **`oro_workflow.transition.assemble`** — Before transition model assembly
10. **`oro_workflow.transition`** — Right before transition actions execute
11. **`oro_workflow.completed`** — Right after transition actions execute
12. **`oro_workflow.finish`** — Final event

**Form events:**
- **`oro_workflow.transition_form_init`** — When transition attribute form initializes
- **`oro_workflow.attribute_form_init`** — When general workflow attributes form initializes

### 6.2 Event Naming Convention

Each event fires as three variants:
```
oro_workflow.{event}                                    # All workflows
oro_workflow.{workflow_name}.{event}                    # Specific workflow
oro_workflow.{workflow_name}.{event}.{transition_name}  # Specific transition
```

**Example:** For transition `approve` in workflow `my_order_workflow`:
- `oro_workflow.guard`
- `oro_workflow.my_order_workflow.guard`
- `oro_workflow.my_order_workflow.guard.approve`

### 6.3 Event Listener Example

```php
// YourBundle/EventListener/OrderWorkflowListener.php
namespace Acme\Bundle\OrderBundle\EventListener;

use Oro\Bundle\WorkflowBundle\Event\WorkflowEvents;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;

class OrderWorkflowListener implements EventSubscriberInterface
{
    public static function getSubscribedEvents(): array
    {
        return [
            'oro_workflow.my_order_workflow.completed.approve' => 'onOrderApproved',
            'oro_workflow.my_order_workflow.guard.reject' => 'guardReject',
        ];
    }

    public function onOrderApproved(WorkflowItemEvent $event): void
    {
        $workflowItem = $event->getWorkflowItem();
        $order = $workflowItem->getEntity();
        // Execute custom logic after approval
    }
}
```

```yaml
# services.yml
services:
  Acme\Bundle\OrderBundle\EventListener\OrderWorkflowListener:
    tags:
      - { name: kernel.event_subscriber }
```

---

## 7. Importing and Extending Workflows

Reuse existing workflow definitions instead of starting from scratch.

### 7.1 Import a Resource File

```yaml
imports:
  - { resource: '@AcmeOrderBundle/Resources/config/oro/workflows/base_order.yml' }
```

### 7.2 Import and Customize an Existing Workflow

```yaml
imports:
  - workflow: b2b_flow_sales         # Existing workflow name
    as: acme_flow_sales              # New workflow name
    replace:                         # Paths within the workflow config to replace
      - steps.qualify.allowed_transitions
      - transitions.close_as_won
```

### 7.3 Conditional Import

```yaml
imports:
  - resource: '@AcmeBundle/Resources/config/oro/workflows/optional.yml'
    import_condition: 'parameter_or_null("acme.feature_enabled") === true'
```

---

## 8. Translation Keys

All user-visible strings are translatable. Define them in:
```
YourBundle/Resources/translations/workflows.en.yml
```

| Context | Translation Key Pattern |
|---------|------------------------|
| Workflow label | `oro.workflow.{name}.label` |
| Step label | `oro.workflow.{name}.step.{step}.label` |
| Transition label | `oro.workflow.{name}.transition.{transition}.label` |
| Transition button text | `oro.workflow.{name}.transition.{transition}.button_label` |
| Transition warning | `oro.workflow.{name}.transition.{transition}.warning_message` |
| Attribute label | `oro.workflow.{name}.attribute.{attribute}.label` |
| Variable label | `oro.workflow.{name}.variable.{variable}.label` |

```yaml
# workflows.en.yml
oro:
  workflow:
    my_order_workflow:
      label: 'Order Approval Workflow'
      step:
        pending:
          label: 'Pending Approval'
        approved:
          label: 'Approved'
      transition:
        approve:
          label: 'Approve'
          button_label: 'Approve Order'
          warning_message: 'Are you sure you want to approve this order?'
        reject:
          label: 'Reject'
          button_label: 'Reject Order'
```

---

## 9. Annotated Complete Example

```yaml
# src/Acme/Bundle/OrderBundle/Resources/config/oro/workflows.yml

workflows:

  acme_order_approval:

    # ---- WORKFLOW META ----
    label: 'Order Approval Workflow'                       # Translation key applied
    entity: Acme\Bundle\OrderBundle\Entity\Order           # Entity this workflow manages
    entity_attribute: order                                # Name of the attribute holding the entity
    is_system: true                                        # Cannot be modified via admin UI
    start_step: pending                                    # Entity starts in 'pending' step
    steps_display_ordered: true                            # Show step wizard in UI
    priority: 100                                          # Higher priority than default workflows
    exclusive_active_groups: [order_approval]              # Only one workflow in this group active
    exclusive_record_groups: [order_processing]            # Prevents simultaneous transitions
    active: true
    applications: [commerce]

    # ---- STEPS ----
    steps:
      pending:
        label: 'Pending Approval'
        order: 10
        allowed_transitions: [approve, reject, request_info]
        entity_acl:
          delete: false                                    # Cannot delete while pending

      awaiting_info:
        label: 'Awaiting Information'
        order: 20
        allowed_transitions: [resubmit]

      approved:
        label: 'Approved'
        order: 30
        is_final: true
        entity_acl:
          update: false                                    # Freeze approved orders
          delete: false

      rejected:
        label: 'Rejected'
        order: 40
        is_final: true

    # ---- ATTRIBUTES ----
    attributes:
      order:
        type: entity
        options:
          class: Acme\Bundle\OrderBundle\Entity\Order

      reviewer_notes:
        type: string
        label: 'Reviewer Notes'

      approved_by:
        type: entity
        options:
          class: Oro\Bundle\UserBundle\Entity\User

      rejection_reason:
        type: string
        property_path: entity.rejectionReason             # Writes back to entity field

    # ---- TRANSITIONS ----
    transitions:

      approve:
        label: 'Approve Order'
        button_label: 'Approve'
        step_to: approved                                  # Move to 'approved' step
        transition_definition: approve_definition
        acl_resource: acme_order_approve                   # User must have this ACL
        display_type: dialog                               # Show as modal
        destination_page: view
        frontend_options:
          icon: 'fa-check'
          class: 'btn-success'
        form_options:
          attribute_fields:
            reviewer_notes:
              form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
              options:
                label: 'Approval Notes'
                required: false

      reject:
        label: 'Reject Order'
        button_label: 'Reject'
        step_to: rejected
        transition_definition: reject_definition
        display_type: dialog
        form_options:
          attribute_fields:
            rejection_reason:
              form_type: Symfony\Component\Form\Extension\Core\Type\TextType
              options:
                required: true
                constraints:
                  - NotBlank: ~

      request_info:
        label: 'Request More Information'
        step_to: awaiting_info
        transition_definition: request_info_definition
        is_unavailable_hidden: true                        # Hide button when not available

      resubmit:
        label: 'Resubmit'
        step_to: pending
        transition_definition: resubmit_definition

    # ---- TRANSITION DEFINITIONS ----
    transition_definitions:

      approve_definition:
        preactions:
          - '@assign_active_user': [$approved_by]          # Auto-populate approver
        preconditions:
          '@acl_granted': 'acme_order_approve'             # Button only visible if ACL granted
        conditions:
          '@and':
            - '@not_blank': [$entity.totalValue]
            - '@greater': [$entity.totalValue, 0]
        actions:
          - '@assign_value': [$entity.status, 'approved']
          - '@assign_value': [$entity.approvedAt, 'now']
          - '@flash_message':
              message: 'Order has been approved successfully'
              type: 'success'

      reject_definition:
        preconditions:
          '@acl_granted': 'acme_order_approve'
        conditions:
          '@not_blank': [$rejection_reason]
        actions:
          - '@assign_value': [$entity.status, 'rejected']
          - '@assign_value': [$entity.rejectionReason, $rejection_reason]

      request_info_definition:
        actions:
          - '@assign_value': [$entity.status, 'info_requested']

      resubmit_definition:
        actions:
          - '@assign_value': [$entity.status, 'pending']

    # ---- ENTITY RESTRICTIONS ----
    entity_restrictions:
      lock_status_after_approval:
        attribute: order
        field: status
        mode: full                                         # Read-only in approved/rejected steps
        step: approved

      lock_status_rejected:
        attribute: order
        field: status
        mode: full
        step: rejected

    # ---- VARIABLE DEFINITIONS ----
    variable_definitions:
      variables:
        auto_approve_limit:
          type: float
          value: 500.00
          label: 'Auto-Approve Limit (configurable via admin UI)'
```

---

## 10. Console Commands Reference

```bash
# Load workflow definitions from YAML into database
php bin/console oro:workflow:definitions:load

# Load only specific workflows
php bin/console oro:workflow:definitions:load --workflows=acme_order_approval

# Load from specific directories
php bin/console oro:workflow:definitions:load --directories=src/Acme/Bundle/OrderBundle

# Activate/deactivate a workflow via CLI (use admin UI or migration for production)
php bin/console oro:workflow:activate acme_order_approval
php bin/console oro:workflow:deactivate acme_order_approval
```

---

## 11. Common Pitfalls

1. **Missing `start_step` or `is_start` transition**: The workflow cannot initialize without one.
2. **Transition not in `allowed_transitions` of current step**: The button will never appear even if all conditions pass.
3. **Precondition vs condition confusion**: Use `preconditions` to hide buttons, `conditions` to block execution. Users get confusing errors if `conditions` rejects something that should have been hidden.
4. **Property path not mapping to entity field**: Use `property_path: entity.fieldName` to sync attribute values back to the entity. Without this, changes to attributes do not persist to the entity.
5. **Recursive trigger chains**: When using triggers, ensure `preconditions` or `exclude_definitions` prevents infinite loops.
6. **`is_system: true` blocks admin UI edits**: Only use for workflows that must not be customized by store administrators.
7. **Missing ACL resource**: If `acl_resource` references a non-existent ACL, the button is always hidden.
