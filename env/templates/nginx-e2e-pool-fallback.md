# Second php-fpm pool (fallback only)

The test stack normally shares the one php-fpm pool: the test server block sets `fastcgi_param ORO_ENV behat_test`
and `ORO_DEBUG 0`, and the spike measured zero cross-hits between the two kernels. Use a second pool only if
cross-hits appear (a prod-env request answered by the test kernel or the reverse).

1. Copy the existing pool file (`/etc/php/<ver>/fpm/pool.d/www.conf`) to `test.conf`; rename the section `[test]`,
   give it its own `listen = /run/php/php<ver>-fpm-test.sock` and `pm.max_children` sized for the e2e workers.
2. Add `env[ORO_ENV] = behat_test` and `env[ORO_DEBUG] = 0` to that pool.
3. Add `upstream php-fpm-test { server unix:/run/php/php<ver>-fpm-test.sock; }` next to the existing upstream and point
   the test block's `fastcgi_pass` at it.
4. Restart through supervisor (`sc restart fpm`, `sc signal HUP nginx`); never systemctl. Each step needs sudo: ask first.
