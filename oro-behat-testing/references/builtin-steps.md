# Built-in Oro Step Definitions

Oro provides 300+ built-in step definitions. This reference covers the most commonly used ones.
For the full list, check the source files in `vendor/oro/platform/`.

## OroMainContext - Navigation, Login, UI

Source: `vendor/oro/platform/src/Oro/Bundle/TestFrameworkBundle/Tests/Behat/Context/OroMainContext.php`

### Login
```gherkin
Given I login as administrator
Given I login as "username" user
```

### Navigation
```gherkin
When I go to System/Localization/Localizations
When I go to Products/ Products
When I go to Marketing/ Landing Pages
# Format: "I go to Menu/ Submenu/ Item" (spaces around / are significant)
```

**RULE — Never hardcode admin URLs.** The backend prefix is project-configurable
(`web_backend_prefix`, e.g. `/admin`, `/control-center`) and Oro's auto-routing
also prepends a per-bundle prefix from `oro/routing.yml`. A literal path like
`I go to "/admin/integration-record/"` will 404 on any project whose backend
prefix differs, and will silently break when a route prefix is renamed.

For backend grids/views, register a menu item under `Resources/config/oro/navigation.yml`
(usually `application_menu` → some `*_tab` → leaf), then drive navigation by
the menu label exposed to the user:

```gherkin
When I go to System/ Integration Logs        # leaf under "system_tab"
When I go to Activities/ CTA Submissions      # leaf under "activities_tab"
```

For the storefront, prefer the locale-aware helper rather than a raw `/`:
```gherkin
Given I visit the storefront page with locale "us-en" and path "/"
```

When you must hit a URL that has no menu entry (e.g. a deep view route), use
the route helper rather than the raw path:
```gherkin
When I open "aaxis_integration_record_view" page with id 42
```

### Buttons and Links
```gherkin
When I click "Create Localization"
When I click "Save and Close"
When I click on "element name"
Then I should see "Button Name" button
Then "Submit" button is disabled
```

### Flash Messages
```gherkin
Then I should see "Localization has been saved" flash message
Then I should not see "Error" flash message
When I close all flash messages
```

### Text and Content Assertions
```gherkin
Then I should see "Region"
Then I should not see "Deleted Item"
Then I should see that "element" contains "text"
Then I should see "5" elements "Grid Row"
```

### Page Structure
```gherkin
Then page has "Localizations" header
Then Page title equals to "Edit Localization"
```

### Alerts and Dialogs
```gherkin
When I accept alert
When I close ui dialog
When I click "OK" in modal window
Then I should see alert with message "Are you sure?"
```

### Screenshots
```gherkin
Then I take screenshot
# Saves to configured artifacts directory - use for debugging only, not assertions
```

### URL Assertions
```gherkin
Then I should see "link text" link with the url matches /pattern/
```

### Wait
```gherkin
When I wait for "element" element to appear
```

## FormContext - Form Operations

Source: `vendor/oro/platform/src/Oro/Bundle/FormBundle/Tests/Behat/Context/FormContext.php`

### Filling Forms
```gherkin
# Fill a named element (defined in behat.yml)
When I fill "Acme Localization Form" with:
  | URL Code | test-001 |

# Fill the default form
When I fill form with:
  | Name  | Test Name  |
  | Email | test@x.com |

# Fill a single field by label
When I fill in "URL Code" with "test-840"

# Type text into a field (triggers keyboard events)
When I type "search term" in "Search"
```

### Saving Forms
```gherkin
When I save form
When I save and close form
When I save and duplicate form
When I save and create new form
```

### Form Value Assertions
```gherkin
Then "Acme Localization Form" must contain values:
  | URL Code | test-001 |

Then form must contain values:
  | Name | Expected Name |

Then Name field should have "Expected Value" value
Then Email field is empty
```

### Field State Assertions
```gherkin
Then the "Field Name" field should be readonly
Then the "Field Name" field should be enabled
Then the "Field Name" field should be disabled
Then the "Checkbox" field should be checked
Then the "Checkbox" field should be unchecked
```

### Checkboxes
```gherkin
When I check "Active" element
When I uncheck "Active" element
Then The "Active" checkbox should be checked
```

### Select Fields
```gherkin
Then I should see the following options for "Country" select:
  | United States |
  | Canada        |
Then the "English" option from "Language" is selected
```

### Validation Errors
```gherkin
Then I should see validation errors:
  | Name | This value should not be blank |
Then I should not see validation errors:
  | Email | |
Then Name is a required field
```

### File Upload
```gherkin
When I upload "file.jpg" file to "Avatar"
```

### Entity Selection Popup
```gherkin
When I open select entity popup for field "Owner"
```

## GridContext - Data Grid Operations

Source: `vendor/oro/platform/src/Oro/Bundle/DataGridBundle/Tests/Behat/Context/GridContext.php`

### Viewing Grid Content
```gherkin
Then I should see "Spanish Product" in grid
Then there is no "French Product" in grid
Then I should see following grid:
  | Name     | SKU    |
  | Product1 | SKU-01 |
Then number of records should be 5
```

### Grid Actions (Row-Level)
```gherkin
When I click edit "Product Name" in grid
When I click delete "Product Name" in grid
When I click view "Product Name" in grid
# The action name matches the action column button text
```

### Record Selection
```gherkin
When I check "Product Name" record in grid
When I uncheck "Product Name" record in grid
When I check first 5 records in grid
```

### Filtering
```gherkin
When I set filter Name as contains "Product"
When I set filter Status as is equal to "Active"
When I set filter "Price" as is equal to "100"
```

### Sorting
```gherkin
When I sort grid by Name
When I sort grid by "Created At" again
```

### Pagination
```gherkin
When I select 25 from per page list dropdown
When I press next page button
Then number of pages should be 3
```

### Inline Editing
```gherkin
When I edit Name as "New Name"
When I edit "Product1" Name as "New Name"
When I edit Name as "New Name" without saving
When I edit Name as "New Name" and cancel
```

### Mass Actions
```gherkin
When I click "Delete" link from mass action dropdown
```

### Named Grids
Most grid steps support a named grid variant:
```gherkin
Then I should see "Product" in "products-grid"
Then number of records in "products-grid" should be 5
When I sort "products-grid" by Name
```

## ConsoleContext - Symfony Commands

Source: `vendor/oro/platform/src/Oro/Bundle/TestFrameworkBundle/Tests/Behat/Context/ConsoleContext.php`

```gherkin
When I run Symfony "oro:search:reindex" command
When I run Symfony "oro:website-search:reindex --class='Oro\Bundle\ProductBundle\Entity\Product'" command
```

Default timeout: 120 seconds. Custom contexts can extend this (e.g., CmsConsoleContext uses 300s).

## Step Cheat Sheet (Most Used)

| Action | Step |
|--------|------|
| Login as admin | `Given I login as administrator` |
| Navigate to page | `When I go to System/Localization/Localizations` |
| Click button | `When I click "Create Localization"` |
| Fill named form | `When I fill "Form Name" with: [table]` |
| Fill single field | `When I fill in "Label" with "value"` |
| Save form | `When I save and close form` |
| Check flash message | `Then I should see "saved" flash message` |
| Assert text visible | `Then I should see "Region"` |
| Assert text hidden | `Then I should not see "Deleted"` |
| Check grid record | `Then I should see "Product" in grid` |
| Assert grid empty | `Then there is no "Product" in grid` |
| Edit grid row | `When I click edit "Product" in grid` |
| Run console command | `When I run Symfony "command" command` |
| Assert form values | `Then "Form" must contain values: [table]` |
| Assert field value | `Then Name field should have "value" value` |
