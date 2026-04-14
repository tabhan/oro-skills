# OroCommerce ACL System Overview

> Source: https://doc.oroinc.com/master/backend/security/acl/

## AGENT QUERY HINTS

Use this file when answering questions like:
- "How does Oro's permission system work?"
- "What are the access levels in OroCommerce?"
- "What is ownership type and how does it affect permissions?"
- "What is the difference between User, BusinessUnit, Organization, and None ownership?"
- "How does Oro decide what a user can see?"
- "What permissions exist for entities?"
- "How does organization context affect data access?"
- "What is BASIC_LEVEL vs LOCAL_LEVEL vs GLOBAL_LEVEL?"

---

## What Is the ACL System?

OroCommerce's Access Control List (ACL) system is built on **OroSecurityBundle**, which extends Symfony's native security framework with a role-based ACL model tailored for multi-organization, multi-business-unit B2B commerce environments.

**WHY it exists:** Standard Symfony security checks "can this user perform action X" (binary yes/no). Oro adds a *scope* dimension: "can this user perform action X on records they own / their business unit owns / their organization owns / globally?" This scope is called the **access level**.

The system has three interlocking concepts:
1. **Permission type** — what action is being checked (VIEW, CREATE, EDIT, etc.)
2. **Ownership type** — who "owns" a given entity record (a User, a Business Unit, an Organization, or Nobody)
3. **Access level** — how broadly a role can exercise a permission (own records only, BU records, org-wide, etc.)

---

## Permission Types

### Entity Permissions

These are the standard CRUD-plus permissions applied to entity classes:

| Permission | Meaning |
|------------|---------|
| `VIEW` | Read / list records |
| `CREATE` | Add new records (access level controls where the record can be created) |
| `EDIT` | Modify existing records |
| `DELETE` | Remove records |
| `ASSIGN` | Reassign ownership of a record to another user/BU |
| `SHARE` | Share a record with other users (Enterprise edition only) |

### Field Permissions

Applied at the individual entity field level (requires Field ACL to be enabled):

| Permission | Meaning |
|------------|---------|
| `VIEW` | Whether the field value is visible |
| `EDIT` | Whether the field value can be changed |

**WHY separate field permissions exist:** Some entities contain sensitive fields (e.g., credit limit, internal notes) that should be hidden from certain roles even when the entity itself is accessible. Field ACL allows exactly this without duplicating entities.

---

## Ownership Types

Every ACL-protected entity must declare an **ownership type**. This declaration is permanent — once set, it cannot be changed without data migration consequences.

**WHY ownership types exist:** The ownership type determines which access levels are *meaningful* for that entity. A record that belongs to nobody (None ownership) cannot have "User-level" access because there is no user-owner to compare against.

| Ownership Type | Available Access Levels | Typical Use Case |
|---------------|------------------------|-----------------|
| `USER` | None, User, Business Unit, Division, Organization, Global | Records created by individual users (orders, tasks, notes) |
| `BUSINESS_UNIT` | None, Business Unit, Division, Organization, Global | Shared BU-level assets (shared price lists, BU-owned accounts) |
| `ORGANIZATION` | None, Organization, Global | Org-wide configuration records |
| `None` | None, Global | System-wide records not tied to any owner (product catalog, currencies) |

**Key insight:** The `None` ownership type gives the *broadest* default access — a record with no owner does not belong to any particular user, BU, or org. It is either accessible to everyone (Global) or nobody (None/deny). This is why product catalog entities typically use `None` ownership.

---

## Access Levels

Access levels define the *scope* of a permission grant within Oro's organizational hierarchy. They form a strict hierarchy from narrowest to broadest:

| Level Name | Constant | Int Value | Scope |
|-----------|----------|-----------|-------|
| None (deny) | `AccessLevel::NONE_LEVEL` | 0 | No access at all |
| User | `AccessLevel::BASIC_LEVEL` | 1 | Only the user's own records |
| Business Unit | `AccessLevel::LOCAL_LEVEL` | 2 | Records owned by the user's assigned business units |
| Division | `AccessLevel::DEEP_LEVEL` | 3 | BU records plus all subordinate (child) business units |
| Organization | `AccessLevel::GLOBAL_LEVEL` | 4 | All records within the current organization |
| Global | `AccessLevel::SYSTEM_LEVEL` | 5 | All records across all organizations (Enterprise only) |

Special constant: `AccessLevel::UNKNOWN` — used internally when the level has not been determined yet.

### Access Level Hierarchy Diagram

```
SYSTEM_LEVEL (Global)
    └── GLOBAL_LEVEL (Organization)
            └── DEEP_LEVEL (Division — BU + children)
                    └── LOCAL_LEVEL (Business Unit)
                            └── BASIC_LEVEL (User — own records)
                                    └── NONE_LEVEL (deny)
```

**WHY the Division level exists:** B2B commerce organizations often have tree structures of business units (regions, districts, branches). Division access lets a regional manager see records for their region and all sub-branches without granting full org-wide access.

---

## ACL Hierarchy — How Decisions Are Made

When a user attempts an action, Oro evaluates in this order:

1. **Object-scope check** — Does the user have permission on this specific entity instance?
2. **Class-scope check** — Does the user have permission on the entity class as a whole?
3. **Default permissions** — Fall back to configured defaults.

The system combines the user's role assignments (which carry access levels) with the record's ownership data (who owns it, which BU, which org) to produce a binary allow/deny decision.

### Ownership Matching Logic

For a `VIEW` permission at `LOCAL_LEVEL` (Business Unit):
- The system checks: "Is this record owned by a business unit that the current user belongs to?"
- If yes: access granted.
- If no: access denied.

For `DEEP_LEVEL`:
- Same check, but also includes child business units of the user's assigned BUs.

For `GLOBAL_LEVEL` (Organization):
- Checks: "Is this record in the same organization as the current user's active organization context?"

---

## Organization Context

In OroCommerce, every user session operates within a single **active organization**. This is critical for multi-org Enterprise installations:

- At login, Oro sets the user's current organization from their preferred organization setting.
- All ACL checks are scoped to this active organization.
- In Enterprise editions, users assigned to multiple organizations can switch contexts.
- The active organization is stored in the security token.

**WHY this matters for access rules:** A user with Organization-level VIEW on `Account` will only see accounts within their *active* organization, not across all orgs (that requires Global/SYSTEM_LEVEL).

To ignore preferred organization for specific token types (e.g., API tokens):

```yaml
# config/packages/oro_organization_pro.yaml
oro_organization_pro:
    ignore_preferred_organization_tokens:
        - Acme\Bundle\DemoBundle\Security\AcmeCustomToken
```

---

## Role-Based Access Control (RBAC) Model

```
User → has Roles → Roles have ACL entries → ACL entries = (Resource, Permission, AccessLevel)
```

- A **role** collects ACL entries granting specific permissions at specific levels.
- A **user** inherits all ACL entries from all their assigned roles.
- When a user has multiple roles, Oro grants the *most permissive* access level across all roles.
- Role hierarchies can be defined for permission inheritance.

---

## Concrete Example: Three Ownership Models

Given: Main Organization with two business units. User John is assigned to Main Business Unit.

**Scenario: Accounts entity with USER ownership**
- John at `BASIC_LEVEL` VIEW: sees only accounts he personally created.
- John at `LOCAL_LEVEL` VIEW: sees all accounts owned by Main Business Unit members.
- John at `DEEP_LEVEL` VIEW: sees Main BU accounts plus Child BU accounts.
- John at `GLOBAL_LEVEL` VIEW: sees all accounts in Main Organization.

**Scenario: Accounts entity with BUSINESS_UNIT ownership**
- `BASIC_LEVEL` is not available (no individual user owner exists).
- John at `LOCAL_LEVEL` VIEW: sees accounts where Main Business Unit is the owner.
- John at `GLOBAL_LEVEL` VIEW: sees all accounts in Main Organization.

**Scenario: Accounts entity with ORGANIZATION ownership**
- Neither `BASIC_LEVEL` nor `LOCAL_LEVEL` is available.
- John at `GLOBAL_LEVEL` VIEW: sees all accounts in Main Organization.

---

## ACL Manager (Programmatic Interface)

The `oro_security.acl.manager` service provides a programmatic API for managing ACL entries:

```php
// Check if ACL is enabled
$manager->isAclEnabled();

// Get security identity for a role
$sid = $manager->getSid('ROLE_MANAGER');

// Get object identity
$oid = $manager->getOid('entity:AcmeDemoBundle:MyEntity');
$oid = $manager->getOid('action:some_action_id');

// Build a permission mask
$builder = $manager->getMaskBuilder($oid);
$mask = $builder->add('VIEW_SYSTEM')->add('EDIT_SYSTEM')->get();

// Set permission
$manager->setPermission($sid, $oid, $mask);

// Persist changes
$manager->flush();
```

### ACL Manager Key Methods

| Method | Purpose |
|--------|---------|
| `getSid($param)` | Get SecurityIdentity for a role name, RoleInterface, UserInterface, or TokenInterface |
| `getOid($object)` | Get ObjectIdentity from domain object or string descriptor `"ExtensionKey:Class"` |
| `getMaskBuilder($oid, $permission)` | Get mask builder for constructing permission bitmasks |
| `setPermission($sid, $oid, $mask)` | Create or update ACE (Access Control Entry) |
| `setFieldPermission($sid, $oid, $field, $mask)` | Create or update field-level ACE |
| `deletePermission($sid, $oid, $mask)` | Remove specific ACE |
| `deleteAllPermissions($sid, $oid)` | Remove all ACEs for a security identity |
| `deleteAcl($oid)` | Delete entire ACL for an object identity |
| `flush()` | Persist all pending ACL changes |

### Object Identity Descriptor Formats

```php
$manager->getOid('entity:AcmeDemoBundleSomeClass')   // flat class name
$manager->getOid('entity:AcmeDemoBundle:SomeEntity')  // bundle:entity shorthand
$manager->getOid('action:some_action_id')             // action resource
```

---

## Key Principles Summary

1. **Immutability of ownership type** — once an entity's ownership type is set, it cannot be changed without significant migration work.
2. **None ownership = broadest scope** — entities with no owner are either globally accessible or blocked; there is no middle ground.
3. **Organization context is always active** — all ACL decisions are scoped to the user's current organization unless using SYSTEM_LEVEL.
4. **Most permissive role wins** — when a user has multiple roles, the highest access level across all roles is used.
5. **Access levels are filtered by ownership type** — only the levels valid for an entity's ownership type appear in the admin UI role editor.
