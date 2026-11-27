<?php

namespace Espo\Custom\Hooks\Account;

use Espo\Core\Hook\Hook\AfterUnrelate;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\UnrelateOptions;

/**
 * CRM-IDINT-001R: identity integrity for Account (AfterUnrelate). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 */
class IdentityAfterUnrelate implements AfterUnrelate
{
    /** Hook order (runs before the platform's own relation hooks, so a refused change is put back before they act on it); the platform's default is 9. */
    public static int $order = 1;

    public function __construct(private IdentityGuard $guard)
    {}

    public function afterUnrelate(
        Entity $entity,
        string $relationName,
        Entity $relatedEntity,
        UnrelateOptions $options
    ): void
    {
        $this->guard->afterUnrelate($entity, $relationName, $relatedEntity);
    }
}
