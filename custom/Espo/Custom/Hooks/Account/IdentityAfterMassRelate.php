<?php

namespace Espo\Custom\Hooks\Account;

use Espo\Core\Hook\Hook\AfterMassRelate;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Query\Select;
use Espo\ORM\Repository\Option\MassRelateOptions;

/**
 * CRM-IDINT-001R: identity integrity for Account (AfterMassRelate). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 */
class IdentityAfterMassRelate implements AfterMassRelate
{
    /** Hook order (runs before the platform's own relation hooks, so a refused change is put back before they act on it); the platform's default is 9. */
    public static int $order = 1;

    public function __construct(private IdentityGuard $guard)
    {}

    public function afterMassRelate(
        Entity $entity,
        string $relationName,
        Select $query,
        array $columnData,
        MassRelateOptions $options
    ): void
    {
        $this->guard->afterMassRelate($entity, $relationName, $query);
    }
}
