# OroCommerce: Workflows, Operations, and Processes

> Source: https://doc.oroinc.com/master/backend/entities-data-management/

---

## AGENT QUERY HINTS

This file answers questions like:
- "How do I create a workflow in OroCommerce?"
- "What is the difference between a workflow, an operation, and a process?"
- "How do I add a button that performs an action on an entity?"
- "How do I define steps, transitions, and guards in a workflow?"
- "What is transition_definitions and how does it differ from transitions?"
- "How do I fire logic automatically when an entity is saved or updated?"
- "How do I write a PHP condition or action class for a workflow?"
- "How do I listen to workflow transition events?"
- "What are post_actions and how do I use them?"
- "What are preconditions vs conditions in an operation?"
- "How does a process trigger work on entity events?"

---

## Choosing the Right Tool: Workflow vs Operation vs Process

This is the most important decision to make before writing any YAML.

```
┌─────────────────────────────────────────────────────────────────┐
│  DECISION GUIDE: Which tool to use?                             │
├─────────────────────────────────────────────────────────────────┤
│  Does the entity move through multiple named STATES             │
│  (e.g., draft → submitted → approved → shipped)?               │
│    YES → Use a WORKFLOW                                         │
│    NO  → Continue below                                         │
├─────────────────────────────────────────────────────────────────┤
│  Is this a ONE-SHOT UI ACTION (button/link) that a user         │
│  explicitly clicks to do something to an entity?                │
│    YES → Use an OPERATION (action)                              │
│    NO  → Continue below                                         │
├─────────────────────────────────────────────────────────────────┤
│  Should logic trigger AUTOMATICALLY when Doctrine fires         │
│  an event (prePersist, postUpdate, etc.) on an entity?          │
│    YES → Use a PROCESS                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Summary Table

| Feature | Workflow | Operation | Process |
|---------|----------|-----------|---------|
| **Trigger** | User clicks transition button | User clicks action button | Doctrine entity event (automatic) |
| **State tracking** | YES — entity moves through named steps | NO — stateless | NO — stateless |
| **Multiple steps** | YES | NO (single action) | NO (single action chain) |
| **UI button** | YES (transition buttons) | YES (configurable button) | NO (invisible to user) |
| **Guards/conditions** | YES | YES (preconditions) | YES (preconditions) |
| **Entity scope** | One entity class (with optional related) | One or more entity classes | One entity class per trigger |
| **Mutually exclusive** | YES (only one active workflow per entity at a time, unless exclusive=false) | NO | NO |
| **Typical use** | Order lifecycle, quote approval, complaint handling | "Approve" button, "Clone" button, "Send Invoice" | Auto-sync on save, cascade field updates, audit trail |

---

## Part 1: Workflows

### What Is a Workflow?

A workflow manages an entity's lifecycle through **named steps** (states) and **transitions** (the moves between states). It is the right tool when an entity's status matters and should be tracked and restricted.

**Examples:** Order approval (draft → submitted → approved → rejected), Quote lifecycle (draft → sent → accepted/declined), Complaint handling (new → investigating → resolved → closed).

### File Location

```
src/Acme/Bundle/DemoBundle/
└── Resources/
    └── config/
        └── oro/
            └── workflows.yml
```

### Complete Workflow Example: Purchase Order Approval

This example shows a realistic order approval workflow with all major YAML keys annotated.

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/workflows.yml

workflows:
    # The unique machine name of the workflow.
    # WHY snake_case: Oro uses this as a service ID and in the database.
    acme_purchase_order_approval:

        # Human-readable label shown in the admin UI.
        label: 'Purchase Order Approval'

        # The Doctrine entity class this workflow manages.
        # WHY: Each workflow is bound to exactly one entity class.
        entity: Acme\Bundle\DemoBundle\Entity\PurchaseOrder

        # The entity property that stores the current step name.
        # WHY: Oro writes the active step label into this field so you
        #      can display it in grids and views without extra queries.
        entity_attribute: purchaseOrder

        # When true, only one workflow of this type can be active per entity.
        # When false, multiple instances can coexist (rare).
        exclusive_active_groups: [purchase_order_management]

        # The step the workflow starts on when first activated.
        start_step: draft

        # ── STEPS ──────────────────────────────────────────────────────────
        # Steps are named STATES. They do not execute logic; they only label
        # where the entity currently is in the process.
        # WHY separate steps from transitions: Oro can show available
        # transitions grouped by current step in the UI.
        steps:
            draft:
                label: 'Draft'
                # Which transitions are available FROM this step.
                allowed_transitions:
                    - submit_for_approval
                    - cancel_order

            pending_approval:
                label: 'Pending Approval'
                allowed_transitions:
                    - approve_order
                    - reject_order
                    - request_changes

            approved:
                label: 'Approved'
                allowed_transitions:
                    - send_to_fulfillment

            rejected:
                label: 'Rejected'
                allowed_transitions:
                    - revise_and_resubmit

            changes_requested:
                label: 'Changes Requested'
                allowed_transitions:
                    - resubmit_with_changes
                    - cancel_order

            cancelled:
                label: 'Cancelled'
                # No transitions from here — terminal step.
                allowed_transitions: []

            in_fulfillment:
                label: 'In Fulfillment'
                allowed_transitions:
                    - mark_fulfilled

            fulfilled:
                label: 'Fulfilled'
                allowed_transitions: []

        # ── ATTRIBUTES ─────────────────────────────────────────────────────
        # Workflow attributes store data SCOPED to the workflow instance.
        # They are persisted in the WorkflowData object, NOT on the entity.
        # WHY: Some data is only relevant during the workflow (e.g., a
        #      rejection reason) and should not pollute the entity schema.
        attributes:
            # The entity itself is always an attribute.
            purchase_order:
                label: 'Purchase Order'
                type: entity
                options:
                    class: Acme\Bundle\DemoBundle\Entity\PurchaseOrder

            # Reviewer note entered during a transition form.
            reviewer_note:
                label: 'Reviewer Note'
                type: string
                property_path: purchaseOrder.reviewerNote

            # Who approved this order — stored on the entity via property_path.
            approved_by:
                label: 'Approved By'
                type: entity
                options:
                    class: Oro\Bundle\UserBundle\Entity\User
                property_path: purchaseOrder.approvedBy

            # A workflow-scoped boolean not persisted on the entity.
            send_notification:
                label: 'Send Notification Email'
                type: boolean

        # ── TRANSITIONS ────────────────────────────────────────────────────
        # Transitions define the MOVES between steps.
        # Each transition references:
        #   step_to: the destination step
        #   transition_definition: the name of the definition (see below)
        #   form_options: optional form shown to the user before executing
        transitions:
            submit_for_approval:
                label: 'Submit for Approval'
                # FontAwesome icon for the transition button.
                # WHY: Improves UX — users recognize icons faster than text.
                message: 'The order will be submitted for manager approval.'
                step_to: pending_approval
                transition_definition: submit_for_approval_definition
                # Display this transition as a button on the entity view page.
                # front_display_type controls where the button appears.
                front_display_type: main
                # Icon shown on the transition button.
                display_type: button

            approve_order:
                label: 'Approve'
                step_to: approved
                transition_definition: approve_order_definition
                # A form will appear in a dialog before the transition executes.
                form_options:
                    attribute_fields:
                        reviewer_note:
                            form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
                            options:
                                required: false
                                label: 'Approval Note'
                        approved_by:
                            form_type: Oro\Bundle\UserBundle\Form\Type\OrganizationUserAclSelectType
                            options:
                                required: true
                                label: 'Approver'

            reject_order:
                label: 'Reject'
                step_to: rejected
                transition_definition: reject_order_definition
                form_options:
                    attribute_fields:
                        reviewer_note:
                            form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
                            options:
                                required: true
                                label: 'Rejection Reason (required)'

            request_changes:
                label: 'Request Changes'
                step_to: changes_requested
                transition_definition: request_changes_definition
                form_options:
                    attribute_fields:
                        reviewer_note:
                            form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
                            options:
                                required: true
                                label: 'Required Changes'

            resubmit_with_changes:
                label: 'Resubmit'
                step_to: pending_approval
                transition_definition: resubmit_definition

            revise_and_resubmit:
                label: 'Revise and Resubmit'
                step_to: pending_approval
                transition_definition: resubmit_definition

            send_to_fulfillment:
                label: 'Send to Fulfillment'
                step_to: in_fulfillment
                transition_definition: fulfillment_definition

            mark_fulfilled:
                label: 'Mark as Fulfilled'
                step_to: fulfilled
                transition_definition: fulfilled_definition

            cancel_order:
                label: 'Cancel Order'
                step_to: cancelled
                transition_definition: cancel_definition

        # ── TRANSITION DEFINITIONS ─────────────────────────────────────────
        # Transition definitions contain the LOGIC: guards, pre-conditions,
        # conditions, pre_actions, and post_actions.
        #
        # WHY separated from transitions: Multiple transitions can share one
        # definition (e.g., revise_and_resubmit and resubmit_with_changes
        # both use resubmit_definition). Keeps YAML DRY.
        transition_definitions:

            submit_for_approval_definition:
                # Guards run BEFORE the transition dialog is shown.
                # If a guard fails, the transition button is hidden entirely.
                # WHY: Guards control VISIBILITY. Use for role-based hiding.
                guards:
                    # Only show the Submit button if the order total > 0.
                    - '@greater_than':
                        parameters:
                            left: $purchaseOrder.totalAmount
                            right: 0

                # Pre-conditions run when the user initiates the transition.
                # If a pre-condition fails, the transition is blocked with
                # a user-visible error message.
                # WHY: Pre-conditions control ELIGIBILITY with feedback.
                pre_conditions:
                    '@and':
                        - '@not_empty':
                            parameters:
                                value: $purchaseOrder.lineItems
                            message: 'Cannot submit an order with no line items.'
                        - '@not_empty':
                            parameters:
                                value: $purchaseOrder.shippingAddress
                            message: 'Please add a shipping address before submitting.'

                # Post-actions execute AFTER the transition succeeds.
                # These are the side effects: update fields, send emails, etc.
                # WHY post vs pre: Post-actions run after the step change is
                # committed, so the entity is already in the new step.
                post_actions:
                    # Set submittedAt to now.
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.submittedAt
                            - '@now'
                    # Dispatch a notification via the message queue.
                    - '@send_email_template':
                        parameters:
                            from: 'system@example.com'
                            to: $purchaseOrder.approver.email
                            template: 'acme_po_submitted'
                            entity: $purchaseOrder

            approve_order_definition:
                guards:
                    # Only managers can see the Approve button.
                    - '@acl_granted':
                        parameters:
                            acl: acme_purchase_order_approve

                pre_conditions:
                    '@not_empty':
                        parameters:
                            value: $approved_by
                        message: 'Approver must be selected.'

                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'approved'
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.approvedAt
                            - '@now'
                    # Call a custom service action registered as a workflow action.
                    - '@acme_notify_requester':
                        parameters:
                            order: $purchaseOrder
                            message: 'Your purchase order has been approved.'

            reject_order_definition:
                guards:
                    - '@acl_granted':
                        parameters:
                            acl: acme_purchase_order_approve

                pre_conditions:
                    '@not_empty':
                        parameters:
                            value: $reviewer_note
                        message: 'A rejection reason is required.'

                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'rejected'
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.rejectedAt
                            - '@now'
                    - '@acme_notify_requester':
                        parameters:
                            order: $purchaseOrder
                            message: 'Your purchase order was rejected.'

            request_changes_definition:
                guards:
                    - '@acl_granted':
                        parameters:
                            acl: acme_purchase_order_approve

                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'changes_requested'

            resubmit_definition:
                pre_conditions:
                    '@not_empty':
                        parameters:
                            value: $purchaseOrder.lineItems
                        message: 'Cannot resubmit an order with no line items.'

                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'pending_approval'
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.resubmittedAt
                            - '@now'

            fulfillment_definition:
                guards:
                    - '@acl_granted':
                        parameters:
                            acl: acme_purchase_order_fulfill

                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'in_fulfillment'
                    # Dispatch an async message to trigger warehouse picking.
                    - '@acme_dispatch_fulfillment_message':
                        parameters:
                            order: $purchaseOrder

            fulfilled_definition:
                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'fulfilled'
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.fulfilledAt
                            - '@now'

            cancel_definition:
                post_actions:
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.status
                            - 'cancelled'
                    - '@assign_value':
                        parameters:
                            - $purchaseOrder.cancelledAt
                            - '@now'
```

### Built-in Workflow Conditions

Conditions are used in `guards` and `pre_conditions`. They evaluate a boolean result.

| Condition | Description | Example |
|-----------|-------------|---------|
| `@not_empty` | Value is non-null and non-empty | Check a required field is filled |
| `@empty` | Value is null or empty | Check a field has no value |
| `@equal` | Two values are equal | Check status equals 'draft' |
| `@not_equal` | Two values differ | Check status is not 'cancelled' |
| `@greater_than` | Left > right | Check total amount > 0 |
| `@less_than` | Left < right | Check quantity < stock level |
| `@greater_than_or_equal` | Left >= right | |
| `@less_than_or_equal` | Left <= right | |
| `@in` | Value is in a list | Check status is in ['draft','rejected'] |
| `@not_in` | Value is NOT in a list | Check status not in ['cancelled','fulfilled'] |
| `@and` | All sub-conditions must pass | Combine multiple checks |
| `@or` | Any sub-condition passes | Alternative conditions |
| `@not` | Inverts a condition | Negate another condition |
| `@acl_granted` | User has ACL permission | Check role-based permission |
| `@is_granted_workflow_transition` | User can execute a workflow transition | |
| `@workflow_available_by_record_group` | Workflow is available for entity's record group | |

### Built-in Workflow Post-Actions

Post-actions execute side effects after a transition.

| Action | Description |
|--------|-------------|
| `@assign_value` | Set an attribute or entity field to a value |
| `@assign_constant_value` | Set a field to a PHP constant value |
| `@format_string` | Format a string and assign to attribute |
| `@copy_values` | Copy values between attributes |
| `@send_email_template` | Send an email using an Oro email template |
| `@redirect` | Redirect after the action |
| `@call_service_method` | Call any registered service method |
| `@run_action_group` | Execute an action group by name |
| `@flash_message` | Show a flash message to the user |
| `@create_entity` | Create and persist a new entity |
| `@find_entity` | Find an existing entity and assign to attribute |
| `@remove_entity` | Delete an entity |
| `@traverse` | Loop over a collection and apply actions to each |

---

## Part 2: PHP Transition Service and Condition Classes

When the built-in conditions and actions are insufficient, write custom PHP classes.

### Custom Workflow Condition

```php
<?php
// src/Acme/Bundle/DemoBundle/Workflow/Condition/OrderHasSufficientBudget.php

namespace Acme\Bundle\DemoBundle\Workflow\Condition;

use Acme\Bundle\DemoBundle\Entity\PurchaseOrder;
use Acme\Bundle\DemoBundle\Service\BudgetService;
use Oro\Component\ConfigExpression\Condition\AbstractCondition;
use Oro\Component\ConfigExpression\ContextAccessorAwareInterface;
use Oro\Component\ConfigExpression\ContextAccessorAwareTrait;
use Oro\Component\ConfigExpression\Exception\InvalidArgumentException;

/**
 * Checks whether the purchase order total is within the requester's
 * approved budget limit.
 *
 * Usage in workflows.yml:
 *   - '@acme_order_has_budget':
 *       parameters:
 *           order: $purchaseOrder
 *
 * WHY a custom condition: Built-in conditions cannot call domain services.
 * This condition encapsulates budget-check logic in a testable, reusable class.
 */
class OrderHasSufficientBudget extends AbstractCondition implements ContextAccessorAwareInterface
{
    use ContextAccessorAwareTrait;

    private const OPTION_ORDER = 'order';

    private mixed $order;

    public function __construct(private readonly BudgetService $budgetService)
    {
    }

    /**
     * The condition name used in YAML: '@acme_order_has_budget'.
     * Must match the service tag alias.
     */
    public function getName(): string
    {
        return 'acme_order_has_budget';
    }

    /**
     * Evaluates the condition against the workflow context.
     * Return true to ALLOW the transition, false to BLOCK it.
     */
    protected function isConditionAllowed(mixed $context): bool
    {
        /** @var PurchaseOrder $order */
        $order = $this->resolveValue($context, $this->order);

        if (!$order instanceof PurchaseOrder) {
            return false;
        }

        $requester = $order->getRequester();
        if ($requester === null) {
            return false;
        }

        return $this->budgetService->isWithinBudget($requester, $order->getTotalAmount());
    }

    /**
     * Initialize from YAML options array.
     * Called during config compilation — not at runtime.
     */
    public function initialize(array $options): static
    {
        if (!isset($options[self::OPTION_ORDER])) {
            throw new InvalidArgumentException(
                sprintf('Option "%s" is required.', self::OPTION_ORDER)
            );
        }

        $this->order = $options[self::OPTION_ORDER];

        return $this;
    }

    /**
     * Return a human-readable error message when this condition fails.
     * This message is shown to the user if used as a pre-condition.
     */
    public function getMessage(): ?string
    {
        return 'The order total exceeds your approved budget limit. Please contact your budget administrator.';
    }
}
```

```yaml
# Register the custom condition as a service:
# src/Acme/Bundle/DemoBundle/Resources/config/services.yml

services:
    acme_demo.workflow.condition.order_has_budget:
        class: Acme\Bundle\DemoBundle\Workflow\Condition\OrderHasSufficientBudget
        arguments:
            - '@acme_demo.service.budget'
        tags:
            # name: oro_workflow.condition registers it as a workflow condition.
            # alias: the YAML key to use (with '@' prefix in YAML).
            - { name: oro_workflow.condition, alias: acme_order_has_budget }
```

### Custom Workflow Action (Post-Action)

```php
<?php
// src/Acme/Bundle/DemoBundle/Workflow/Action/NotifyOrderRequester.php

namespace Acme\Bundle\DemoBundle\Workflow\Action;

use Acme\Bundle\DemoBundle\Entity\PurchaseOrder;
use Acme\Bundle\DemoBundle\Service\NotificationService;
use Oro\Component\Action\Action\AbstractAction;
use Oro\Component\Action\Action\ActionInterface;
use Oro\Component\ConfigExpression\ContextAccessorAwareInterface;
use Oro\Component\ConfigExpression\ContextAccessorAwareTrait;

/**
 * Sends a notification to the purchase order requester.
 *
 * Usage in workflows.yml:
 *   - '@acme_notify_requester':
 *       parameters:
 *           order: $purchaseOrder
 *           message: 'Your order has been approved.'
 *
 * WHY a custom action: This encapsulates notification logic so it can be
 * reused across multiple workflow transitions and tested in isolation.
 */
class NotifyOrderRequester extends AbstractAction implements ContextAccessorAwareInterface
{
    use ContextAccessorAwareTrait;

    private mixed $order;
    private mixed $message;

    public function __construct(
        private readonly NotificationService $notificationService,
    ) {
        parent::__construct();
    }

    /**
     * Execute the action.
     * $context is the WorkflowItem's data bag — access attributes via resolveValue.
     */
    protected function executeAction(mixed $context): void
    {
        /** @var PurchaseOrder $order */
        $order = $this->resolveValue($context, $this->order);
        $message = $this->resolveValue($context, $this->message);

        if (!$order instanceof PurchaseOrder || $order->getRequester() === null) {
            return;
        }

        $this->notificationService->notifyUser(
            user: $order->getRequester(),
            subject: 'Purchase Order Status Update',
            body: $message,
            relatedEntity: $order,
        );
    }

    /**
     * Parse and store options from the YAML parameters block.
     */
    public function initialize(array $options): ActionInterface
    {
        $this->order = $options['order'] ?? throw new \InvalidArgumentException(
            'Option "order" is required for @acme_notify_requester action.'
        );
        $this->message = $options['message'] ?? '';

        return $this;
    }
}
```

```yaml
# Register the custom action:
services:
    acme_demo.workflow.action.notify_requester:
        class: Acme\Bundle\DemoBundle\Workflow\Action\NotifyOrderRequester
        arguments:
            - '@acme_demo.service.notification'
        tags:
            # alias must match the '@acme_notify_requester' key used in YAML.
            - { name: oro_action.action, alias: acme_notify_requester }
```

---

## Part 3: Workflow Event Listeners

OroWorkflowBundle dispatches Symfony events at each stage of a workflow transition. Use these to add cross-cutting concerns (logging, integration calls, cache invalidation) without modifying workflow YAML.

### Available Workflow Events

| Event Constant | When It Fires | Class |
|----------------|--------------|-------|
| `workflow.before_transit` | Before any transition executes (guards already passed) | `WorkflowTransitionEvent` |
| `workflow.transit` | After the transition commits (step changed) | `WorkflowTransitionEvent` |
| `workflow.after_transit` | After all post-actions complete | `WorkflowTransitionEvent` |
| `workflow.leave` | Entity leaves its current step | `WorkflowStepEvent` |
| `workflow.enter` | Entity enters the new step | `WorkflowStepEvent` |
| `workflow.announce` | Before the transition is announced (fires for each available transition) | `WorkflowTransitionEvent` |
| `workflow.guard` | During guard evaluation | `GuardEvent` |

### Workflow Event Listener Example

```php
<?php
// src/Acme/Bundle/DemoBundle/EventListener/PurchaseOrderWorkflowListener.php

namespace Acme\Bundle\DemoBundle\EventListener;

use Acme\Bundle\DemoBundle\Entity\PurchaseOrder;
use Acme\Bundle\DemoBundle\Service\AuditLogService;
use Oro\Bundle\WorkflowBundle\Entity\WorkflowItem;
use Oro\Bundle\WorkflowBundle\Event\WorkflowTransitionEvent;
use Psr\Log\LoggerInterface;

/**
 * Listens to purchase order workflow transitions to:
 * 1. Write audit log entries for compliance.
 * 2. Invalidate caches on approval.
 * 3. Log unexpected transition failures.
 *
 * WHY a listener instead of a post_action: Listeners are ideal for
 * cross-cutting concerns that should NOT appear in the workflow YAML
 * (logging, cache invalidation, external audit systems).
 * Post-actions are better for domain-specific workflow side effects.
 */
class PurchaseOrderWorkflowListener
{
    public function __construct(
        private readonly AuditLogService $auditLogService,
        private readonly LoggerInterface $logger,
    ) {
    }

    /**
     * Fires before the transition executes.
     * Use this to prepare data or validate externally.
     * Throwing an exception here PREVENTS the transition.
     */
    public function onBeforeTransit(WorkflowTransitionEvent $event): void
    {
        $workflowItem = $event->getWorkflowItem();
        $transition = $event->getTransition();
        $entity = $this->extractPurchaseOrder($workflowItem);

        if ($entity === null) {
            return;
        }

        $this->logger->info('Purchase order workflow transition starting.', [
            'order_id' => $entity->getId(),
            'transition' => $transition->getName(),
            'from_step' => $workflowItem->getCurrentStep()?->getName(),
        ]);
    }

    /**
     * Fires after the transition completes and the new step is set.
     * The entity is now in the new step. Use this for audit logging.
     * Exceptions here do NOT roll back the transition.
     */
    public function onAfterTransit(WorkflowTransitionEvent $event): void
    {
        $workflowItem = $event->getWorkflowItem();
        $transition = $event->getTransition();
        $entity = $this->extractPurchaseOrder($workflowItem);

        if ($entity === null) {
            return;
        }

        // Write an immutable audit log entry for compliance tracking.
        $this->auditLogService->logWorkflowTransition(
            entityClass: PurchaseOrder::class,
            entityId: $entity->getId(),
            transitionName: $transition->getName(),
            toStep: $workflowItem->getCurrentStep()?->getName() ?? 'unknown',
            performedBy: $workflowItem->getUpdatedBy(),
        );
    }

    private function extractPurchaseOrder(WorkflowItem $workflowItem): ?PurchaseOrder
    {
        $entity = $workflowItem->getEntity();

        return $entity instanceof PurchaseOrder ? $entity : null;
    }
}
```

```yaml
# Register the listener:
# src/Acme/Bundle/DemoBundle/Resources/config/services.yml

services:
    acme_demo.event_listener.purchase_order_workflow:
        class: Acme\Bundle\DemoBundle\EventListener\PurchaseOrderWorkflowListener
        arguments:
            - '@acme_demo.service.audit_log'
            - '@logger'
        tags:
            - name: kernel.event_listener
              # Only fires for transitions on the specific workflow.
              # Remove the "event" suffix pattern to listen to ALL workflows.
              event: 'workflow.before_transit'
              method: onBeforeTransit
            - name: kernel.event_listener
              event: 'workflow.after_transit'
              method: onAfterTransit
```

---

## Part 4: Operations (Actions)

### What Is an Operation?

An **operation** (also called an "action") is a one-shot UI action — typically a button or link — that performs a specific action on one or more entities. Operations do NOT track state. Use them for actions that happen once without moving the entity through named steps.

**Examples:** "Approve Order" button that sets a single status field, "Clone Product" button, "Send Invoice" button, "Export to PDF" button, "Recalculate Totals" button.

### File Location

```
src/Acme/Bundle/DemoBundle/
└── Resources/
    └── config/
        └── oro/
            └── actions.yml
```

### Complete Operation Example: Approve Order Button

This shows a realistic "Approve Order" button with conditional display, a confirmation dialog, and side effects.

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/actions.yml

operations:
    # Machine name of the operation — must be unique across all bundles.
    acme_approve_purchase_order:

        # Human-readable label shown on the button.
        label: 'Approve Order'

        # Which entity types this operation applies to.
        # WHY: Oro uses this to decide where to show the button.
        entities:
            - Acme\Bundle\DemoBundle\Entity\PurchaseOrder

        # Where to display the operation button/link.
        # Options: view (entity view page), list (datagrid row action),
        #          update (edit form), view_list (multiple places).
        # WHY: Different contexts need different UI placements.
        for_all_entities: false
        for_all_datagrids: false
        datagrids:
            - acme-purchase-orders-grid

        # ── BUTTON CONFIGURATION ────────────────────────────────────────────
        button_options:
            # Icon class (FontAwesome).
            icon: 'fa-check'
            # CSS class added to the button.
            class: 'btn btn-success'
            # 'group' renders multiple operations as a dropdown.
            group: ~
            # Page template for rendering the button.
            template: ~

        # ── FRONT-END OPTIONS ───────────────────────────────────────────────
        frontend_options:
            # Show a confirmation dialog before executing.
            # WHY: Approval is irreversible — users should confirm intent.
            confirmation:
                title: 'Confirm Approval'
                message: 'Are you sure you want to approve this purchase order?'
                ok_text: 'Approve'
                cancel_text: 'Cancel'

        # ── PRECONDITIONS (before dialog/form is shown) ─────────────────────
        # If a precondition fails, the button is HIDDEN.
        # WHY: Different from conditions — preconditions control visibility,
        #      conditions control execution eligibility.
        preconditions:
            '@and':
                # Only show the button if the order is in 'pending_approval' status.
                - '@equal':
                    parameters:
                        left: $entity.status
                        right: 'pending_approval'
                # Only show the button to users with the approve permission.
                - '@acl_granted':
                    parameters:
                        acl: acme_purchase_order_approve

        # ── CONDITIONS (before execution) ──────────────────────────────────
        # If a condition fails after the user confirms, execution is blocked
        # with an error message.
        conditions:
            '@and':
                - '@not_empty':
                    parameters:
                        value: $entity.lineItems
                    message: 'Cannot approve an order with no line items.'
                - '@greater_than':
                    parameters:
                        left: $entity.totalAmount
                        right: 0
                    message: 'Cannot approve an order with zero total.'

        # ── FORM OPTIONS ────────────────────────────────────────────────────
        # Optional: show a form in a dialog before executing.
        # The user fills this in, then the values are available in 'actions'.
        # If you don't need form input, omit this section entirely.
        form_options:
            attribute_fields:
                approver_note:
                    form_type: Symfony\Component\Form\Extension\Core\Type\TextareaType
                    options:
                        label: 'Approval Note (optional)'
                        required: false
                        attr:
                            rows: 3

        # ── ATTRIBUTES ──────────────────────────────────────────────────────
        # Operation-scoped attributes, similar to workflow attributes.
        # The 'entity' attribute is always implicitly available.
        attributes:
            approver_note:
                label: 'Approver Note'
                type: string

        # ── ACTIONS (executed on confirmation) ──────────────────────────────
        # The actual side effects that happen when the operation runs.
        # These use the same action syntax as workflow post_actions.
        actions:
            # Set status on the entity.
            - '@assign_value':
                parameters:
                    - $entity.status
                    - 'approved'

            # Set approved timestamp.
            - '@assign_value':
                parameters:
                    - $entity.approvedAt
                    - '@now'

            # Copy the note from the form attribute to the entity.
            - '@assign_value':
                parameters:
                    - $entity.reviewerNote
                    - $approver_note

            # Persist the entity via the custom service.
            - '@call_service_method':
                parameters:
                    service: doctrine
                    method: getManagerForClass
                    method_parameters:
                        - 'Acme\Bundle\DemoBundle\Entity\PurchaseOrder'
                    attribute: $em
            - '@call_service_method':
                parameters:
                    service: $em
                    method: flush

            # Send a notification.
            - '@acme_notify_requester':
                parameters:
                    order: $entity
                    message: 'Your purchase order has been approved.'

            # Show confirmation flash message to the admin.
            - '@flash_message':
                parameters:
                    message: 'Purchase order approved successfully.'
                    type: success

    # ── SECOND OPERATION EXAMPLE: Clone Order ───────────────────────────────
    acme_clone_purchase_order:
        label: 'Clone Order'

        entities:
            - Acme\Bundle\DemoBundle\Entity\PurchaseOrder

        button_options:
            icon: 'fa-copy'
            class: 'btn btn-default'

        frontend_options:
            # No confirmation dialog for non-destructive actions.
            confirmation: ~

        preconditions:
            '@acl_granted':
                parameters:
                    acl: acme_purchase_order_create

        # No conditions needed — cloning is always allowed if preconditions pass.

        attributes:
            # 'new_order' will hold the cloned entity.
            new_order:
                label: 'New Order'
                type: entity
                options:
                    class: Acme\Bundle\DemoBundle\Entity\PurchaseOrder

        actions:
            # Use a custom action that handles the deep-copy logic.
            - '@acme_clone_entity':
                parameters:
                    source: $entity
                    attribute: $new_order

            # Redirect to the edit page of the new order.
            - '@redirect':
                parameters:
                    route: acme_demo_purchase_order_update
                    route_parameters:
                        id: $new_order.id
```

---

## Part 5: Processes

### What Is a Process?

A **process** (or process definition) fires automatically in response to **Doctrine entity lifecycle events** — not user actions. It is the right tool when you need to react to entity changes transparently, without a UI button or step-tracking.

**Examples:** When a PurchaseOrder is approved (status changes to 'approved'), automatically create an ERP sync message. When a CustomerUser is deactivated, cancel their pending orders. When a product price changes, invalidate related price list caches.

**Key distinction:** Processes are event-driven and invisible to the user. They are NOT replacements for domain event listeners — processes are configuration-driven (YAML) and use the same action system as workflows and operations.

### File Location

```
src/Acme/Bundle/DemoBundle/
└── Resources/
    └── config/
        └── oro/
            └── processes.yml
```

### Complete Process Example: Auto-Sync to ERP on Order Approval

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/processes.yml

processes:
    # Machine name — must be unique.
    acme_sync_approved_order_to_erp:

        # Human-readable label (shown in the process administration UI).
        label: 'Sync Approved Purchase Order to ERP'

        # Whether this process is active.
        # WHY: Allows disabling without deleting the configuration.
        enabled: true

        # Priority when multiple processes fire on the same event.
        # Lower number = higher priority (runs first).
        order: 10

        # ── TRIGGERS ────────────────────────────────────────────────────────
        # Triggers define WHEN the process fires.
        # Each trigger listens to a Doctrine event on a specific entity.
        #
        # Available events:
        #   create  → Doctrine postPersist (entity just created)
        #   update  → Doctrine postUpdate (entity just updated)
        #   delete  → Doctrine postRemove (entity just deleted)
        #
        # WHY use 'update' + field check: A process fires on every update,
        # so we narrow it with 'field' and 'queued' to avoid over-triggering.
        triggers:
            -
                # Doctrine event type.
                type: update

                # Entity class that triggers the process.
                entity: Acme\Bundle\DemoBundle\Entity\PurchaseOrder

                # Only fire if this specific field changed.
                # WHY: Prevents the process from firing on every unrelated update.
                # If omitted, fires on ANY field change.
                field: status

                # Run asynchronously via the message queue.
                # WHY: ERP sync is slow. Running it synchronously blocks
                # the HTTP response. Always queue slow I/O.
                queued: true

                # Only fire if queued is true AND the entity meets this condition.
                # Evaluated BEFORE queuing to avoid unnecessary messages.
                # Uses the same expression syntax as workflow conditions.

            -
                # Also fire on create — in case an order is pre-approved at creation.
                type: create
                entity: Acme\Bundle\DemoBundle\Entity\PurchaseOrder
                queued: true

        # ── PRECONDITIONS ────────────────────────────────────────────────────
        # Evaluated BEFORE actions execute (at dequeue time if queued).
        # If false, the process is skipped without error.
        # WHY: The entity state may have changed between queue time and execution.
        #      Always re-check conditions at execution time.
        preconditions:
            '@equal':
                parameters:
                    left: $entity.status
                    right: 'approved'

        # ── ACTIONS ──────────────────────────────────────────────────────────
        # What the process does when it fires and preconditions pass.
        # Same action syntax as workflow post_actions.
        actions:
            # Set a sync-pending flag (optional — for idempotency tracking).
            - '@assign_value':
                parameters:
                    - $entity.erpSyncStatus
                    - 'pending'

            # Dispatch a message to the ERP integration message queue.
            - '@call_service_method':
                parameters:
                    service: acme_demo.integration.erp_sync_producer
                    method: dispatchOrderSync
                    method_parameters:
                        - $entity

            # Log the dispatch for audit purposes.
            - '@call_service_method':
                parameters:
                    service: logger
                    method: info
                    method_parameters:
                        - 'ERP sync dispatched for approved purchase order'
                        - { order_id: $entity.id, status: $entity.status }

    # ── SECOND PROCESS EXAMPLE: Cancel Pending Orders on User Deactivation ──
    acme_cancel_orders_on_user_deactivate:
        label: 'Cancel Pending Orders When User Is Deactivated'
        enabled: true
        order: 20

        triggers:
            -
                type: update
                entity: Oro\Bundle\UserBundle\Entity\User
                field: enabled
                queued: true

        preconditions:
            # Only run if the user was just deactivated (enabled = false).
            '@equal':
                parameters:
                    left: $entity.enabled
                    right: false

        actions:
            # Find all pending orders for this user and cancel them.
            # '@traverse' loops over a collection and applies actions to each item.
            - '@find_entities':
                parameters:
                    class: Acme\Bundle\DemoBundle\Entity\PurchaseOrder
                    where:
                        requester: $entity
                        status: 'pending_approval'
                    attribute: $pendingOrders

            - '@traverse':
                parameters:
                    array: $pendingOrders
                    actions:
                        - '@assign_value':
                            parameters:
                                - $.status
                                - 'cancelled'
                        - '@assign_value':
                            parameters:
                                - $.cancelledAt
                                - '@now'
```

### Process Trigger Reference

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `type` | YES | `create`, `update`, `delete` | Doctrine lifecycle event |
| `entity` | YES | FQCN | Entity class to watch |
| `field` | NO | field name | Only fire if this field changed (update only) |
| `queued` | NO | `true`/`false` | Run via message queue (recommended for slow ops) |
| `time_shift` | NO | seconds (int) | Delay execution by N seconds (queued only) |
| `cron` | NO | cron expression | Run on a schedule instead of entity event |

---

## Part 6: CLI Commands for Workflows, Operations, and Processes

```bash
# List all registered workflows with their status.
php bin/console oro:workflow:list

# Load workflow definitions from YAML files into the database.
# Run after adding or modifying workflows.yml.
php bin/console oro:workflow:definitions:load

# Activate a workflow by name.
php bin/console oro:workflow:activate acme_purchase_order_approval

# Deactivate a workflow (existing entities keep their current step).
php bin/console oro:workflow:deactivate acme_purchase_order_approval

# List all registered process definitions.
php bin/console oro:process:list

# Load process definitions from YAML into the database.
php bin/console oro:process:load-definitions

# Enable/disable a specific process definition.
php bin/console oro:process:enable acme_sync_approved_order_to_erp
php bin/console oro:process:disable acme_sync_approved_order_to_erp

# Trigger all processes for a specific entity manually (useful for testing).
php bin/console oro:process:execute acme_sync_approved_order_to_erp --id=42

# After any change to workflows.yml, actions.yml, or processes.yml:
php bin/console cache:clear
```

---

## Part 7: Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Forgetting `php bin/console oro:workflow:definitions:load` | Workflow YAML is ignored — old DB definition runs | Always reload after YAML changes |
| Using `conditions` where `preconditions` is needed | Button shows when it should be hidden | `preconditions` = visibility control; `conditions` = execution eligibility |
| Writing slow I/O in a synchronous post_action | HTTP request times out | Use `queued: true` on processes, or dispatch a message queue message |
| Referencing `$entity` in operations as if it were a workflow attribute | Operations use `$entity` (the main entity), not a named attribute | In operations, `$entity` always refers to the primary entity |
| Using `guards` in an operation (they don't exist in operations) | YAML error or ignored | Operations use `preconditions` and `conditions` only |
| Forgetting `@` prefix on conditions/actions | YAML parses as a string, condition silently never runs | All conditions and actions must start with `@` |
| Modifying the entity in a `workflow.before_transit` listener and throwing an exception | May leave entity in inconsistent state | Only throw exceptions in `before_transit` before any entity changes |
| Using `update` trigger without `field` filter on a frequently-updated entity | Process fires on every save, even for unrelated changes | Always add `field: specificField` to narrow trigger scope |
| Setting `exclusive_active_groups` to different groups for the same entity | Multiple workflows can activate simultaneously — conflicting states | Use the same `exclusive_active_groups` value for mutually exclusive workflows |

---

## Part 8: Workflow in Action — Checking Current Step in PHP

```php
<?php
// How to get the current workflow step of an entity from PHP code.

use Oro\Bundle\WorkflowBundle\Model\WorkflowManager;

class PurchaseOrderService
{
    public function __construct(
        private readonly WorkflowManager $workflowManager,
    ) {
    }

    /**
     * Returns the name of the current workflow step for a purchase order.
     * Returns null if no workflow is active on this entity.
     */
    public function getCurrentStep(PurchaseOrder $order): ?string
    {
        // Get all active workflow items for this entity.
        $workflowItems = $this->workflowManager->getWorkflowItemsByEntity($order);

        foreach ($workflowItems as $workflowItem) {
            // Filter to our specific workflow if multiple could be active.
            if ($workflowItem->getWorkflowName() === 'acme_purchase_order_approval') {
                return $workflowItem->getCurrentStep()?->getName();
            }
        }

        return null;
    }

    /**
     * Programmatically transit to a step (use sparingly — prefer UI transitions).
     * Useful for migrations or test fixtures.
     */
    public function transitOrder(PurchaseOrder $order, string $transitionName): void
    {
        $workflowItems = $this->workflowManager->getWorkflowItemsByEntity($order);

        foreach ($workflowItems as $workflowItem) {
            if ($workflowItem->getWorkflowName() === 'acme_purchase_order_approval') {
                // transit() validates guards and conditions, executes post_actions.
                $this->workflowManager->transit($workflowItem, $transitionName);
                return;
            }
        }

        throw new \RuntimeException(
            sprintf('No active workflow found for order %d.', $order->getId())
        );
    }
}
```

```yaml
# Register the service:
services:
    acme_demo.service.purchase_order:
        class: Acme\Bundle\DemoBundle\Service\PurchaseOrderService
        arguments:
            - '@oro_workflow.manager'
```

---

## Summary Checklist

### When creating a Workflow:
- [ ] Define steps (states) and which transitions are allowed from each
- [ ] Define transitions: label, step_to, form_options if needed
- [ ] Define transition_definitions: guards, pre_conditions, post_actions
- [ ] Run `oro:workflow:definitions:load` after YAML changes
- [ ] Activate the workflow: `oro:workflow:activate <name>`
- [ ] Clear cache: `cache:clear`

### When creating an Operation:
- [ ] Define which entities it applies to
- [ ] Configure button_options and frontend_options (confirmation dialog)
- [ ] Use preconditions for visibility, conditions for eligibility
- [ ] Add form_options only if user input is needed before execution
- [ ] Clear cache after YAML changes

### When creating a Process:
- [ ] Choose the correct trigger type (create/update/delete)
- [ ] Add field filter if the trigger should only fire on specific field changes
- [ ] Use `queued: true` for any I/O-heavy actions
- [ ] Always add preconditions to re-check state at execution time (entity may have changed since queuing)
- [ ] Run `oro:process:load-definitions` after YAML changes
- [ ] Clear cache after changes
