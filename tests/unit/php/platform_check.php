<?php
/**
 * CRM-IDINT-001R (A16, rule 3C): checks the custom PHP and the unit-test stand-ins against
 * the real, pinned EspoCRM sources. Run with the reference path in the environment
 * variable CRM_PLATFORM_REFERENCE (read by tests/unit/test_platform_reference.py).
 *
 *   php platform_check.php load  <reference> <custom dir> <php file>
 *       Loads one custom class through the platform's own autoloader. PHP itself checks,
 *       when the class is declared, that every interface it implements and every class it
 *       extends exists and that every method signature is compatible; a missing symbol or
 *       an incompatible signature is a fatal error, so a non-zero exit is a failure.
 *       Prints "OK <class> <kind>:<hook methods>" on success.
 *   php platform_check.php named <reference> <custom dir> <json file>
 *       The json file lists [class, required interface or null, where it is named]. Prints one
 *       line per class that does not exist, or does not implement the interface it is named for.
 *   php platform_check.php dump  <stubs file>
 *       Loads the stand-ins WITHOUT the platform and prints every symbol they declare in
 *       an Espo\ namespace (outside Espo\Custom\) with its methods, as JSON.
 *   php platform_check.php compare <reference> <dump json file>
 *       Checks each declared stand-in symbol exists in the platform and that each declared
 *       method exists there with the same parameters, defaults, variadics and return type.
 *       Prints one line per problem; no output means the stand-ins are consistent.
 */

function usage(): never
{
    fwrite(STDERR, "usage: see the header of this file\n");
    exit(2);
}

function autoload(string $reference, ?string $custom = null): void
{
    require $reference . '/vendor/autoload.php';

    if ($custom !== null) {
        spl_autoload_register(function (string $class) use ($custom): void {
            $prefix = 'Espo\\Custom\\';

            if (str_starts_with($class, $prefix)) {
                $file = $custom . '/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';

                if (is_file($file)) {
                    require $file;
                }
            }
        });
    }
}

function typeString(?ReflectionType $type): string
{
    if ($type === null) {
        return '';
    }

    if ($type instanceof ReflectionUnionType || $type instanceof ReflectionIntersectionType) {
        $parts = array_map(fn($t) => typeString($t), $type->getTypes());
        sort($parts);

        return implode($type instanceof ReflectionUnionType ? '|' : '&', $parts);
    }

    /** @var ReflectionNamedType $type */
    $name = $type->getName();

    return ($type->allowsNull() && $name !== 'mixed' && $name !== 'null' ? '?' : '') . $name;
}

function methodShape(ReflectionMethod $method): array
{
    $params = [];

    foreach ($method->getParameters() as $p) {
        $params[] = [
            'type' => typeString($p->getType()),
            'variadic' => $p->isVariadic(),
            'optional' => $p->isOptional(),
            'byRef' => $p->isPassedByReference(),
        ];
    }

    return [
        'static' => $method->isStatic(),
        'params' => $params,
        'return' => typeString($method->getReturnType()),
    ];
}

$mode = $argv[1] ?? '';

if ($mode === 'load') {
    [, , $reference, $custom, $file] = $argv + [null, null, null, null, null];

    if (!$reference || !$custom || !$file) {
        usage();
    }

    autoload($reference, $custom);

    $relative = substr($file, strlen($custom) + 1, -4);
    $class = 'Espo\\Custom\\' . str_replace('/', '\\', $relative);

    if (!class_exists($class) && !interface_exists($class)) {
        fwrite(STDERR, "FAIL $class is not declared by $file\n");
        exit(1);
    }

    $ref = new ReflectionClass($class);
    $kinds = [];

    // The hook methods the platform would register: public methods other than those it ignores.
    if (str_contains($class, '\\Hooks\\')) {
        $hookMethods = array_values(array_diff(
            array_map(fn($m) => $m->getName(), array_filter($ref->getMethods(), fn($m) => $m->isPublic())),
            ['__construct', 'getDependencyList', 'inject']
        ));
        $hookMethods = array_values(array_filter($hookMethods, fn($m) => !str_starts_with($m, 'set')));
        $fromInterfaces = [];

        foreach ($ref->getInterfaces() as $interface) {
            if (str_starts_with($interface->getName(), 'Espo\\Core\\Hook\\Hook\\')) {
                foreach ($interface->getMethods() as $m) {
                    $fromInterfaces[] = $m->getName();
                }
            }
        }

        sort($hookMethods);
        sort($fromInterfaces);

        if ($hookMethods !== $fromInterfaces) {
            fwrite(STDERR, "FAIL $class public methods [" . implode(',', $hookMethods) .
                '] are not exactly those of the Espo\\Core\\Hook\\Hook interfaces it implements [' .
                implode(',', $fromInterfaces) . "]\n");
            exit(1);
        }

        $kinds[] = implode(',', $hookMethods);
    }

    echo "OK $class " . implode(';', $kinds) . "\n";
    exit(0);
}

if ($mode === 'named') {
    [, , $reference, $custom, $listFile] = $argv + [null, null, null, null, null];

    if (!$reference || !$custom || !$listFile) {
        usage();
    }

    autoload($reference, $custom);
    $problems = [];

    foreach (json_decode((string) file_get_contents($listFile), true) as [$class, $interface, $where]) {
        if (!class_exists($class) && !interface_exists($class)) {
            $problems[] = "$where names $class, which does not exist";

            continue;
        }

        if ($interface !== null && !in_array($interface, class_implements($class), true)) {
            $problems[] = "$where names $class, which does not implement $interface";
        }
    }

    echo implode("\n", $problems), $problems ? "\n" : '';
    exit(0);
}

if ($mode === 'dump') {
    $stubs = $argv[2] ?? null;

    if (!$stubs) {
        usage();
    }

    $before = array_merge(get_declared_classes(), get_declared_interfaces(), get_declared_traits());
    require $stubs;
    $after = array_merge(get_declared_classes(), get_declared_interfaces(), get_declared_traits());
    $out = [];

    foreach (array_diff($after, $before) as $name) {
        if (!str_starts_with($name, 'Espo\\') || str_starts_with($name, 'Espo\\Custom\\')) {
            continue;
        }

        $ref = new ReflectionClass($name);

        if ($ref->getFileName() !== realpath($stubs)) {
            continue;
        }

        $methods = [];

        foreach ($ref->getMethods() as $m) {
            if ($m->getDeclaringClass()->getName() === $name) {
                $methods[$m->getName()] = methodShape($m);
            }
        }

        $out[$name] = ['interface' => $ref->isInterface(), 'methods' => $methods];
    }

    echo json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
    exit(0);
}

if ($mode === 'compare') {
    [, , $reference, $dumpFile] = $argv + [null, null, null, null];

    if (!$reference || !$dumpFile) {
        usage();
    }

    autoload($reference);
    $dump = json_decode((string) file_get_contents($dumpFile), true);
    $problems = [];

    foreach ($dump as $name => $stub) {
        if (!class_exists($name) && !interface_exists($name) && !trait_exists($name)) {
            $problems[] = "stand-in declares $name, which the platform does not have";

            continue;
        }

        $real = new ReflectionClass($name);

        foreach ($stub['methods'] as $method => $shape) {
            if (!$real->hasMethod($method)) {
                $problems[] = "stand-in $name declares $method(), which the platform does not have";

                continue;
            }

            $actual = methodShape($real->getMethod($method));

            if ($actual['static'] !== $shape['static']) {
                $problems[] = "stand-in $name->$method() differs in static";
            }

            if ($actual['return'] !== $shape['return']) {
                $problems[] = "stand-in $name->$method() returns '{$shape['return']}', the platform '{$actual['return']}'";
            }

            if (count($actual['params']) !== count($shape['params'])) {
                $problems[] = "stand-in $name->$method() takes " . count($shape['params']) .
                    ' parameters, the platform ' . count($actual['params']);

                continue;
            }

            foreach ($actual['params'] as $i => $p) {
                if ($p !== $shape['params'][$i]) {
                    $problems[] = "stand-in $name->$method() parameter " . ($i + 1) . ' is ' .
                        json_encode($shape['params'][$i]) . ', the platform ' . json_encode($p);
                }
            }
        }
    }

    echo implode("\n", $problems), $problems ? "\n" : '';
    exit(0);
}

usage();
