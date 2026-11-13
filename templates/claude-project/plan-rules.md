<!-- aaxis-oro:plan-rules:start -->
## Extension design rules

- Designing or implementing an Oro extension (event, DI tag, service override, datagrid, workflow/operation, MQ,
  config, layout, JS) means consulting `aaxis-oro:solutions` and the Oro docs first, and citing both in the plan and
  in the change description.
- The planner's Step 5b dispatches `aaxis-oro:architect-gate` as a 4th plan review (beside security, performance, ux);
  a plan with an uncited or inappropriate extension-point choice does not pass.
<!-- aaxis-oro:plan-rules:end -->
