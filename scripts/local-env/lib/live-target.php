<?php
// oro: ">=7.0.0"
// Usage: ORO_ENV=<env> ORO_DEBUG=0 php live-target.php <project-root> <env>
// Boots the kernel of <env> and prints what it really resolves to, one key=value per line: current_database
// (live query) plus the resolved container parameters for search prefixes, MQ transport, GridFS and sessions.
$project = $argv[1] ?? '';
$env = $argv[2] ?? '';
if (!is_file($project . '/vendor/autoload_runtime.php') || $env === '') {
    fwrite(STDERR, "usage: php live-target.php <project-root> <env>\n");
    exit(64);
}
chdir($project);
require_once $project . '/vendor/autoload_runtime.php';

return function () use ($env) {
    $kernel = new AppKernel($env, false);
    $kernel->boot();
    $c = $kernel->getContainer();
    try {
        echo 'current_database=', $c->get('doctrine')->getConnection()->fetchOne('select current_database()'), "\n";
    } catch (\Throwable $e) {
        echo "current_database=\n";
    }
    $dsn = $c->hasParameter('database_dsn') ? (string) $c->getParameter('database_dsn') : '';
    if ($dsn === '') {
        // A freshly cleared prod container can lack the parameter; the live connection still knows its target.
        try {
            $p = $c->get('doctrine')->getConnection()->getParams();
            $dsn = sprintf('%s://%s:%s/%s', $p['driver'] ?? 'pgsql', $p['host'] ?? '', $p['port'] ?? '', $p['dbname'] ?? '');
        } catch (\Throwable $e) {
            $dsn = '';
        }
    }
    echo 'database_dsn=', $dsn, "\n";
    foreach (['search_engine_dsn', 'website_search_engine_dsn', 'message_queue_transport_dsn',
        'gaufrette_adapter.public', 'gaufrette_adapter.private', 'session_handler_dsn'] as $p) {
        echo $p, '=', $c->hasParameter($p) ? $c->getParameter($p) : '', "\n";
    }

    return new class implements \Symfony\Component\Runtime\RunnerInterface {
        public function run(): int
        {
            return 0;
        }
    };
};
