# Runtime debugging

## 6. Runtime debugging — logger + `oro:logger:level`, never edit monolog

To trace why a runtime behaviour misfires (precondition denying, voter rejecting, autocomplete
returning wrong rows):

1. Inject `Psr\Log\LoggerInterface` into the suspect class (real `@logger` in services.yml; use
   `new NullLogger()` only in unit tests).
2. Add `$this->logger->debug('ClassName.event', [...inputs/outputs...])` at branching points,
   using stable `ClassName.event` label prefixes so greps stay clean across sessions. Log the
   inputs/outputs of decisions, not whole object graphs.
3. Toggle at runtime — **never** edit `config_prod.yml` fingers_crossed/min_level:
   ```bash
   c oro:logger:level debug '15 minutes'    # enable (a \DateInterval string)
   c oro:logger:level warning '0 seconds'   # revert immediately
   ```
   This flips a system-config setting Oro's monolog processor reads — no FPM restart, no cache clear.
4. Truncate the log, trigger the flow, `grep -E 'YourClass\.|YourLabel' var/logs/prod.log`.
5. Revert the level when done; keep the logger injection (good for next time).

