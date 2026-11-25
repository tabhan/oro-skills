# Runtime debugging: logger + `oro:logger:level`, never edit monolog

To trace a misfiring runtime behaviour (precondition denying, voter rejecting, autocomplete returning wrong rows):

1. Inject `Psr\Log\LoggerInterface` into the suspect class (real `@logger` in services.yml; `new NullLogger()` only in unit tests).
2. Add `$this->logger->debug('ClassName.event', [...inputs/outputs...])` at branching points, with stable
   `ClassName.event` prefixes so greps stay clean. Log decision inputs/outputs, not whole object graphs.
3. Toggle at runtime, **never** by editing `config_prod.yml` fingers_crossed/min_level:
   ```bash
   c oro:logger:level debug '15 minutes'    # enable (a \DateInterval string)
   c oro:logger:level warning '0 seconds'   # revert immediately
   ```
   It flips a system-config setting Oro's monolog processor reads: no FPM restart, no cache clear.
4. Truncate the log, trigger the flow, `grep -E 'YourClass\.|YourLabel' var/logs/prod.log`.
5. Revert the level when done; keep the logger injection.
