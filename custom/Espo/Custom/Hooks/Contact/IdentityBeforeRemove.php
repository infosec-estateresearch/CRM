<?php

namespace Espo\Custom\Hooks\Contact;

use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001: identity integrity for Contact (BeforeRemove). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 *
 * @implements BeforeRemove<Entity>
 */
class IdentityBeforeRemove implements BeforeRemove
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeRemove(Entity $entity, mixed ...$rest): void
    {
        $this->guard->beforeRemove($entity);
    }
}
