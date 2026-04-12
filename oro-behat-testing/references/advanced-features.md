# Advanced Features

## Oro Behat CLI Options

Beyond standard Behat flags, Oro adds useful discovery options:

```bash
# Discover what's available
behat --available-suites          # List all registered test suites
behat --available-references      # List all pre-loaded fixture references
behat --available-features        # List all registered feature files
behat --contexts                  # List all registered context classes
behat --elements                  # List all registered elements

# Control message queue consumers during tests
behat --consumers=2               # Number of MQ consumers (default: 2)
behat --do-not-run-consumer       # Disable background MQ processing
```

These are invaluable when writing tests — use `--available-references` to find
entity aliases available in fixtures, and `--elements` to find form elements.

## Watch Mode (Interactive Development)

Speed up test development with watch mode:

```bash
behat --watch -- path/to/feature.feature
```

- Tests pause on failure instead of exiting
- Press ENTER to continue from current line
- Enter a line number to jump to a specific step
- Stop at the final step when writing new tests
- Ctrl+C to exit

Start from a specific line:
```bash
behat --watch --watch-from=25 -- path/to/feature.feature
```

## Multiple Browser Sessions

Oro defines six named sessions for different viewports and multi-user testing:

| Session | Viewport | Use Case |
|---------|----------|----------|
| `first_session` | 1920x1080 | Default desktop |
| `second_session` | 1920x1080 | Second user |
| `system_session` | 1920x1080 | ACL/permission changes |
| `375_session` | 375x640 | Mobile narrow |
| `640_session` | 640x1100 | Tablet |
| `mobile_session` | iPhone 12 Pro | Mobile emulation |

### Multi-User Testing

```gherkin
# Initialize session aliases
Given sessions:
  | First User  | first_session  |
  | Second User | second_session |

# Login users into specific sessions
Given I login as "admin" and use in first_session as Admin
Given I login as administrator and use in "first_session" as "Admin"

# Switch between sessions
Then I operate as the Admin
Then I continue as the User
Then I switch to the "Beginning" session

# Named actor syntax
Given I operate as "Manager" under "second_session"
Given here is the "Buyer" under "first_session"
```

### Responsive Testing

```gherkin
# Use mobile session for responsive tests
Given sessions:
  | Mobile User | mobile_session |
Then I operate as the Mobile User
# All subsequent steps run at iPhone 12 Pro viewport
```

## Secrets Variables

Store sensitive test credentials in `.behat-secrets.yml` (git-ignored):

```yaml
secrets:
    login:
        username: admin
        password: s3crEtPas$
    api:
        token: abc123
```

Reference in scenarios with `<Secret:path.notation>`:

```gherkin
And I fill form with:
  | Username | <Secret:login.username> |
  | Password | <Secret:login.password> |
```

## VariableStorage - Cross-Step Data Passing

Pass data between steps within a scenario using in-memory storage:

```php
use Oro\Bundle\TestFrameworkBundle\Tests\Behat\Context\VariableStorage;

// Store a value in one step
VariableStorage::storeData('orderId', $order->getId());

// Retrieve in another step
$id = VariableStorage::getStoredData('orderId');
```

In Gherkin, use `$alias$` syntax (resolved by `normalizeValue()`):
```gherkin
When I create order and remember its ID as "newOrder"
Then I go to order page with ID "$newOrder$"
```

## Page Objects

For custom pages with routes, define page objects for clean navigation:

Register in behat.yml:
```yaml
oro_behat_extension:
    pages:
        UserProfileView:
            class: Oro\Bundle\UserBundle\Tests\Behat\Page\UserProfileView
            route: 'oro_user_profile_view'
```

Create the page class:
```php
namespace Acme\Bundle\MyBundle\Tests\Behat\Page;

use Oro\Bundle\TestFrameworkBundle\Behat\Element\Page;

class MyEntityView extends Page
{
    // Page-specific helper methods
}
```

Use in features:
```gherkin
And I open User Profile View page
And I should be on User Profile View page
```

## Embedded Form (iFrame) Support

For forms rendered inside iFrames, use the `embedded-id` option:

```yaml
oro_behat_extension:
    elements:
        CustomContactUsForm:
            selector: 'div#page'
            class: Oro\Bundle\TestFrameworkBundle\Behat\Element\Form
            options:
                embedded-id: embedded-form
                mapping:
                    First name: 'custom_bundle_contactus_contact_request[firstName]'
                    Last name: 'custom_bundle_contactus_contact_request[lastName]'
```

The `embedded-id` tells the element factory to switch into the iFrame before
interacting with form fields, and switch back after.

## @behat-test-env Tag - Service Overrides

Use this tag to load custom service definitions from `Tests/Behat/parameters.yml`,
enabling mock services during tests:

```gherkin
@behat-test-env
Feature: Payment Processing
  Tests that need mocked external services
```

In `Tests/Behat/parameters.yml`:
```yaml
services:
    # Override the real payment client with a mock
    acme.payment.client:
        class: Acme\Bundle\PaymentBundle\Tests\Behat\Mock\PaymentClientMock
        public: true
```

Use this pattern for:
- Mocking external API clients (payment gateways, shipping APIs)
- Replacing slow services with fast test doubles
- Injecting predictable responses for deterministic tests

## Fixture Security Context

Load fixtures with a specific user context:

```gherkin
@fixture-OroBundle:data.yml?user_reference=custom_user
@fixture-OroBundle:data.yml?user=admin
```

The `user_reference` option sets the security token to the referenced user
during fixture loading, ensuring entities are created with proper ownership.

## Debugging Steps

```gherkin
# Pause execution and wait for manual input (press RETURN to continue)
And I wait for action

# Take a screenshot (saved to artifacts directory)
And I take screenshot
```

Use `I wait for action` during development to inspect browser state manually.
Remove before committing.
