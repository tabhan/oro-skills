# Additional Built-in Contexts

Beyond OroMainContext, FormContext, GridContext, and ConsoleContext, Oro provides
several other contexts useful for custom test scenarios.

## CommerceMainContext - Storefront / Buyer Login

Source: `vendor/oro/commerce/src/Oro/Bundle/ApplicationBundle/Tests/Behat/Context/CommerceMainContext.php`

Use when testing storefront (frontend) pages as a buyer.

```gherkin
# Login as a buyer on the storefront
Given I login as AmandaRCole@example.org buyer
Given I signed in as AmandaRCole@example.org on the store frontend
Given I signed in as user@test.com with password Pa$$w0rd on the store frontend

# Keep cookies from previous session
Given I login as AmandaRCole@example.org buyer in old session
```

Automatically disables CSS animations in `@BeforeStep` for test stability.

Register in behat.yml:
```yaml
contexts:
    - Oro\Bundle\ApplicationBundle\Tests\Behat\Context\CommerceMainContext
```

## EmailContext - Email Assertions

Source: `vendor/oro/platform/src/Oro/Bundle/EmailBundle/Tests/Behat/Context/EmailContext.php`

Use when testing features that send email notifications.

**Requires Mailcatcher** configured:
```
ORO_MAILER_DSN=smtp://127.0.0.1:1025
ORO_MAILER_WEB_URL=http://127.0.0.1:1080/
```

```gherkin
# Check email was sent with content
Then Email should contains the following "some text" text
Then An email containing the following "some text" text was sent

# Check specific email fields
Then Email should contains the following:
  | From    | admin@example.com |
  | To      | user1@example.com |
  | Subject | Test Subject      |
  | Body    | Test Body         |

# Check email with subject matching
Then email with Subject "RFQ received" containing the following was sent:
  | To   | buyer@example.com |
  | Body | Thank you         |

# Verify email was NOT sent
Then email with Subject "Rejected" was not sent

# Date assertions
Then email date less than "+3 days"
Then email date greater than "-1 day"

# Follow links in emails
Then I follow "Confirm" link from the email
Then I follow link from the email

# Remember and replay email links
Then I remember "Confirm" link from the email
Then I follow remembered "Confirm" link from the email

# Download file from email link
Then take the link from email and download the file from this link
Then take the "Download" link from email and download the file from this link

# Verify downloaded file content
Then Downloaded export file should contain following rows in any order:
  | Col1 | Col2 |
  | A    | B    |

# Send email template programmatically
Given I send email template "welcome_template" to "admin"
```

Register in behat.yml:
```yaml
contexts:
    - Oro\Bundle\EmailBundle\Tests\Behat\Context\EmailContext
```

## ImportExportContext - CSV Import/Export

Source: `vendor/oro/platform/src/Oro/Bundle/ImportExportBundle/Tests/Behat/Context/ImportExportContext.php`

Use when testing custom entity import/export functionality.

```gherkin
# Download and inspect templates
When I download "Contact" Data Template file
When I download "Contact" Data Template file with processor "contacts.export"
Then I see Name column
Then I don't see Internal ID column
Then I see the following columns in the downloaded csv template:
  | Name | Email | Phone |

# Prepare import data
When I fill template with data:
  | Name    | Email              |
  | Contact | contact@test.com   |
When I fill import file with data:
  | Name    | Email              |
  | Contact | contact@test.com   |

# Run import
When I import file
When I import downloaded template file
When I import file with strategy "add or replace"
When I try import file
When I validate file
When I validate file with strategy "add or replace"

# Run export
When I run export
When I run export for "Contact"
Then I download export file

# Verify export content
Then The last exported file contains the following data:
  | Name    | Email |
  | Contact | c@t   |
Then Exported file for "Contact" contains at least the following columns:
  | Name    | Email |
  | Contact | c@t   |
Then Exported file for "Contact" contains following rows in any order:
  | Name | Email |

# Import results
Then I should receive the import results email containing the text "processed: 5"
Then I should see validation message "some message"
Then I should see import error "some error"

# Re-import exported file
When I import exported file

# Multi-tab import
When I open "Products" import tab

# Change batch size
Given I change the export batch size to 100
```

Register in behat.yml:
```yaml
contexts:
    - Oro\Bundle\ImportExportBundle\Tests\Behat\Context\ImportExportContext
```

## ACLContext - Permissions and Access Control

Source: `vendor/oro/platform/src/Oro/Bundle/SecurityBundle/Tests/Behat/Context/ACLContext.php`

Use when testing features that depend on role permissions.

```gherkin
# Set entity permissions for a role
Given user permissions on View Account is set to None
Given administrator permissions on Edit Contact is set to Global

# Access levels: None, User, Business Unit, Division, Organization, Global

# Login under specific organization (multi-org)
Given I am logged in under "Acme Corp" organization
```

Register in behat.yml:
```yaml
contexts:
    - Oro\Bundle\SecurityBundle\Tests\Behat\Context\ACLContext
```

## WysiwygContext - Rich Text Editor

Source: `vendor/oro/platform/src/Oro/Bundle/FormBundle/Tests/Behat/Context/WysiwygContext.php`

Use when filling WYSIWYG editor fields in custom forms.

```gherkin
When I fill in WYSIWYG "CMS Page Content" with "Content"
Then I should see text matching "pattern" in WYSIWYG editor
Then I should not see text matching "pattern" in WYSIWYG editor
When I click on "WysiwygFileTypeBlock" with title "File name" in WYSIWYG editor
When I click on "WysiwygTextTypeBlock" in WYSIWYG editor
```

Register in behat.yml:
```yaml
contexts:
    - Oro\Bundle\FormBundle\Tests\Behat\Context\WysiwygContext
```

## BrowserTabContext - Multi-Tab Workflows

Source: `vendor/oro/platform/src/Oro/Bundle/TestFrameworkBundle/Tests/Behat/Context/BrowserTabContext.php`

Use when testing workflows that open new browser tabs.

```gherkin
Then a new browser tab is opened
Then a new browser tab is opened and I switch to it
When I open a new browser tab and set "tab1" alias for it
When I set alias "tab1" for the current browser tab
When I switch to the browser tab "tab1"
When I close the current browser tab
When I close the browser tab "tab1"
```

Register in behat.yml:
```yaml
contexts:
    - Oro\Bundle\TestFrameworkBundle\Tests\Behat\Context\BrowserTabContext
```

## Context Registration Summary

Include contexts based on what your tests need:

| Context | When to Include |
|---------|----------------|
| `OroMainContext` | Always (login, nav, buttons, assertions) |
| `FormContext` | Always (form filling, saving, validation) |
| `GridContext` | When testing datagrid pages |
| `ConsoleContext` | When running console commands in tests |
| `CommerceMainContext` | When testing storefront as buyer |
| `EmailContext` | When testing email notifications |
| `ImportExportContext` | When testing CSV import/export |
| `ACLContext` | When testing permission-dependent features |
| `WysiwygContext` | When testing WYSIWYG editor fields |
| `BrowserTabContext` | When testing multi-tab workflows |
