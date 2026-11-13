# POC bundle (`AppBundle`): spikes and one-offs

Throwaway code (spikes, experiments, one-off scripts, fixtures nobody ships) lives in ONE place:
`src/Aaxis/Bundle/AppBundle`.

- The bundle registers itself and is git-ignored through its own `AppBundle/.gitignore` containing `*`
  (never `.git/info/exclude`, so every clone ignores it the same way). Create the folder with that file when first needed.
- Nothing may depend on it: no `use ...AppBundle\...`, no service id, route, translation key or config from it
  in shipped code. If a spike proves a design, rebuild it in a real bundle.
- It is never committed. A diff, commit or plan that contains an `AppBundle/` path is a defect:
  review and the architect gate both check it.

Check (must print nothing):

```bash
git diff --name-only <base>...HEAD | grep 'AppBundle/'
git ls-files | grep 'AppBundle/'
```
