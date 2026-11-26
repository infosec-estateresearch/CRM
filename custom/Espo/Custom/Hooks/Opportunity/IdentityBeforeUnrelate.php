<?php

namespace Espo\Custom\Hooks\Opportunity;

use Espo\Core\Hook\Hook\BeforeUnrelate;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001: identity integrity for Opportunity (BeforeUnrelate). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 *
 * @implements BeforeUnrelate<Entity>
 */
class IdentityBeforeUnrelate implements BeforeUnrelate
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeUnrelate(Entity $entity, string $relationName, Entity $foreignEntity, mixed ...$rest): void
    {
        $this->guard->beforeUnrelate($entity, $relationName, $foreignEntity);
    }
}
