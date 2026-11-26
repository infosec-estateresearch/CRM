<?php

namespace Espo\Custom\Hooks\Opportunity;

use Espo\Core\Hook\Hook\AfterRelate;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RelateOptions;

/**
 * CRM-IDINT-001R: identity integrity for Opportunity (AfterRelate). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 */
class IdentityAfterRelate implements AfterRelate
{
    /** Hook order (runs before the platform's own relation hooks, so a refused change is put back before they act on it); the platform's default is 9. */
    public static int $order = 1;

    public function __construct(private IdentityGuard $guard)
    {}

    public function afterRelate(
        Entity $entity,
        string $relationName,
        Entity $relatedEntity,
        array $columnData,
        RelateOptions $options
    ): void
    {
        $this->guard->afterRelate($entity, $relationName, $relatedEntity);
    }
}
