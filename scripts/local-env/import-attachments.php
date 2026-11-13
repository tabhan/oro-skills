<?php
// oro: ">=7.0.0"
// Usage: ORO_ENV=<env> php import-attachments.php <project-root> <dir containing attachments/>
// Writes every file into the app's `attachments` Gaufrette filesystem (GridFS when configured) through
// FileManager, skipping names already stored. Never touches public/media. Exit 1 when any file fails.
$project = $argv[1] ?? '';
$src = rtrim($argv[2] ?? '', '/') . '/attachments';
if (!is_file($project . '/vendor/autoload_runtime.php') || !is_dir($src)) {
    fwrite(STDERR, "usage: php import-attachments.php <project-root> <dir containing attachments/>\n");
    exit(64);
}
chdir($project);
require_once $project . '/vendor/autoload_runtime.php';

return function (array $context) use ($src) {
    $kernel = new AppKernel($context['ORO_ENV'], (bool) ($context['ORO_DEBUG'] ?? false));
    $kernel->boot();
    $fm = $kernel->getContainer()->get('oro_attachment.file_manager');
    $start = microtime(true);
    $written = $skipped = $failed = 0;
    foreach (new DirectoryIterator($src) as $file) {
        if (!$file->isFile()) {
            continue;
        }
        $name = $file->getFilename();
        if ($fm->hasFile($name)) {
            $skipped++;
            continue;
        }
        try {
            $fm->writeFileToStorage($file->getPathname(), $name);
            $written++;
        } catch (\Throwable $e) {
            $failed++;
            fwrite(STDERR, "FAIL $name: " . $e->getMessage() . "\n");
        }
    }
    printf("written=%d skipped=%d failed=%d seconds=%.1f adapter=%s\n", $written, $skipped, $failed, microtime(true) - $start, $fm->getAdapterDescription());

    return $failed ? 1 : 0;
};
