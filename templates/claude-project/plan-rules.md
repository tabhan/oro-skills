<!-- aaxis-oro:plan-rules:start -->
## Extension design rules

- Designing or implementing an Oro extension (event, DI tag, service override, datagrid, workflow/operation, MQ,
  config, layout, JS) means consulting `aaxis-oro:solutions` and the Oro docs first, and citing both in the plan.
- After the plan is written and before Execute, run `aaxis-oro:architect-gate` on it and save its verdict to
  `.oro-ai/task/<TICKET>/architect-gate.md`. REJECT blocks Execute until the plan is fixed and the gate passes.
<!-- aaxis-oro:plan-rules:end -->
