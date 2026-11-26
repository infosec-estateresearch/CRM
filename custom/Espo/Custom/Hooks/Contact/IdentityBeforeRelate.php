<?php

namespace Espo\Custom\Hooks\Contact;

use Espo\Core\Hook\Hook\BeforeRelate;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001: identity integrity for Contact (BeforeRelate). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 *
 * @implements BeforeRelate<Entity>
 */
class IdentityBeforeRelate implements BeforeRelate
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeRelate(Entity $entity, string $relationName, Entity $foreignEntity, mixed ...$rest): void
    {
        $this->guard->beforeRelate($entity, $relationName, $foreignEntity);
    }
}
